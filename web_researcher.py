"""
Web research per flagged account using Serper (Google Search).
Max 3 queries per account, 90-day recency filter, 45-second total cap.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp

import config

logger = logging.getLogger(__name__)

SERPER_URL = config.SERPER_URL
MAX_QUERIES = config.MAX_RESEARCH_QUERIES
TIMEOUT_SECONDS = config.RESEARCH_TIMEOUT_SECONDS
RECENCY_DAYS = config.NEWS_RECENCY_DAYS


@dataclass
class NewsItem:
    headline: str
    publication: str
    date: Optional[str]
    url: str
    summary: str


@dataclass
class ResearchResult:
    company: str
    recent_news: list[NewsItem] = field(default_factory=list)
    research_confidence: str = "Low"
    research_notes: str = ""


_QUERY_TEMPLATES = [
    "{company} nursing shortage 2025 2026",
    "{company} workforce retention news",
    "{company} financial wellness employee benefits",
    "{company} nurse turnover staffing",
    "{company} hospital news {year}",
]


def _pick_queries(company_name: str, stage: str, notes_summary: str) -> list[str]:
    """
    Select the 3 most likely queries to yield relevant results.
    Prioritise financial/benefit queries for early stages; workforce/retention
    for mid-to-late stages; general news always included.
    """
    year = datetime.now(timezone.utc).year
    rendered = [t.format(company=company_name, year=year) for t in _QUERY_TEMPLATES]

    stage_lower = (stage or "").lower()
    if any(k in stage_lower for k in ("contract", "verbal", "internal review")):
        # Late stage — workforce ROI and financial wellness are most persuasive
        order = [3, 2, 4, 0, 1]
    elif any(k in stage_lower for k in ("cold",)):
        order = [4, 0, 2, 1, 3]
    else:
        order = [0, 2, 4, 1, 3]

    selected = [rendered[i] for i in order[: MAX_QUERIES]]
    return selected


def _is_recent(date_str: Optional[str], cutoff: datetime) -> bool:
    if not date_str:
        return True  # can't filter what we don't know
    try:
        # Serper returns dates like "May 1, 2025" or "2025-05-01"
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                return dt >= cutoff
            except ValueError:
                continue
    except Exception:
        pass
    return True  # default to include if unparseable


def _extract_items(raw_results: list[dict], cutoff: datetime) -> list[NewsItem]:
    items = []
    for r in raw_results:
        date_str = r.get("date")
        if not _is_recent(date_str, cutoff):
            continue
        headline = r.get("title", "").strip()
        url = r.get("link", "")
        publication = r.get("source", r.get("displayLink", ""))
        snippet = r.get("snippet", "")
        # Build a 2-sentence summary from the snippet
        sentences = [s.strip() for s in snippet.split(".") if s.strip()]
        summary = ". ".join(sentences[:2])
        if summary and not summary.endswith("."):
            summary += "."
        if headline and url:
            items.append(NewsItem(
                headline=headline,
                publication=publication,
                date=date_str,
                url=url,
                summary=summary or snippet[:200],
            ))
    return items


class WebResearcher:
    def __init__(self):
        self._api_key: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    def _key(self) -> str:
        if self._api_key is None:
            self._api_key = config.search_api_key()
        return self._api_key

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _search(self, query: str) -> list[dict]:
        session = await self._session_get()
        headers = {"X-API-KEY": self._key(), "Content-Type": "application/json"}
        payload = {"q": query, "num": 10, "tbs": f"qdr:m3"}  # last 3 months
        timeout = aiohttp.ClientTimeout(total=15)

        async with session.post(
            SERPER_URL, json=payload, headers=headers, timeout=timeout
        ) as resp:
            if resp.status != 200:
                logger.warning("Serper returned %d for query: %s", resp.status, query)
                return []
            data = await resp.json()
            return data.get("organic", [])

    async def research(
        self,
        company_name: str,
        stage: str = "",
        notes_summary: str = "",
    ) -> ResearchResult:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RECENCY_DAYS)
        queries = _pick_queries(company_name, stage, notes_summary)
        all_items: list[NewsItem] = []
        notes: list[str] = []

        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                tasks = [self._search(q) for q in queries]
                raw_batches = await asyncio.gather(*tasks, return_exceptions=True)

                for i, batch in enumerate(raw_batches):
                    if isinstance(batch, Exception):
                        logger.warning("Search query %d failed: %s", i, batch)
                        notes.append(f"Query {i+1} failed: {type(batch).__name__}")
                        continue
                    items = _extract_items(batch, cutoff)
                    all_items.extend(items)

        except TimeoutError:
            notes.append(f"Research timed out after {TIMEOUT_SECONDS}s")
            logger.warning("Research timed out for %s", company_name)

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_items: list[NewsItem] = []
        for item in all_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)

        if not unique_items:
            notes.append("No recent news found")

        confidence = (
            "High" if len(unique_items) >= 3
            else "Moderate" if len(unique_items) >= 1
            else "Low"
        )

        logger.info(
            "Research for %s: %d items, confidence=%s",
            company_name, len(unique_items), confidence,
        )

        return ResearchResult(
            company=company_name,
            recent_news=unique_items[:5],  # cap at 5 items
            research_confidence=confidence,
            research_notes=" | ".join(notes) if notes else "Research completed successfully",
        )
