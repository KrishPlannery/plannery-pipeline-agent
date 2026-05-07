"""
Attio REST API client.
Rate-limit-aware with exponential backoff on 429. Typed exceptions for
non-retryable 4xx errors. All calls logged with timestamp and response code.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import aiohttp

import config

logger = logging.getLogger(__name__)

ATTIO_BASE = config.ATTIO_BASE_URL
MAX_RETRIES = 5
BASE_BACKOFF = 1.0  # seconds


class AttioError(Exception):
    """Non-retryable Attio API error (4xx except 429)."""
    def __init__(self, status: int, message: str):
        super().__init__(f"Attio {status}: {message}")
        self.status = status


@dataclass
class AttioContact:
    name: str
    email: Optional[str]
    title: Optional[str]


@dataclass
class AttioRecord:
    record_id: str
    company_name: str
    last_email_interaction: Optional[datetime]
    last_calendar_interaction: Optional[datetime]
    contacts: list[AttioContact] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class PipelineEntry:
    entry_id: str
    record_id: str
    pipeline: str
    stage: str
    cold_since: Optional[datetime]
    record: Optional[AttioRecord] = None


class AttioClient:
    def __init__(self):
        self._token = None
        self._session: Optional[aiohttp.ClientSession] = None

    def _headers(self) -> dict:
        if self._token is None:
            self._token = config.attio_api_key()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Any:
        url = f"{ATTIO_BASE}{path}"
        session = await self._session_get()
        attempt = 0

        while True:
            start = time.monotonic()
            async with session.request(
                method, url, headers=self._headers(), **kwargs
            ) as resp:
                elapsed = (time.monotonic() - start) * 1000
                logger.info(
                    "Attio %s %s → %d (%.0fms)",
                    method.upper(), path, resp.status, elapsed,
                )

                if resp.status == 200 or resp.status == 201:
                    return await resp.json()

                if resp.status == 429:
                    if attempt >= MAX_RETRIES:
                        raise AttioError(429, "Rate limit exceeded after max retries")
                    retry_after = float(resp.headers.get("Retry-After", BASE_BACKOFF * (2 ** attempt)))
                    logger.warning("Attio 429 — backing off %.1fs (attempt %d)", retry_after, attempt + 1)
                    await asyncio.sleep(retry_after)
                    attempt += 1
                    continue

                # Non-retryable 4xx
                if 400 <= resp.status < 500:
                    body = await resp.text()
                    raise AttioError(resp.status, body[:200])

                # 5xx — retry with backoff
                if resp.status >= 500:
                    if attempt >= MAX_RETRIES:
                        raise AttioError(resp.status, "Server error after max retries")
                    backoff = BASE_BACKOFF * (2 ** attempt)
                    logger.warning("Attio %d — backing off %.1fs", resp.status, backoff)
                    await asyncio.sleep(backoff)
                    attempt += 1
                    continue

                raise AttioError(resp.status, "Unexpected response")

    # ------------------------------------------------------------------
    # Pipeline reads
    # ------------------------------------------------------------------

    async def get_pipeline_entries(self, list_slug: str) -> list[PipelineEntry]:
        entries = []
        limit = 500
        offset = 0

        while True:
            data = await self._request(
                "POST",
                f"/lists/{list_slug}/entries/query",
                json={"limit": limit, "offset": offset},
            )
            batch = data.get("data", [])
            for raw in batch:
                entry = self._parse_entry(raw, list_slug)
                if entry:
                    entries.append(entry)

            if len(batch) < limit:
                break
            offset += limit

        logger.info("Fetched %d entries from %s", len(entries), list_slug)
        return entries

    def _parse_entry(self, raw: dict, pipeline: str) -> Optional[PipelineEntry]:
        try:
            entry_id = raw["id"]["entry_id"]
            record_id = raw["parent_record_id"]
            attrs = raw.get("entry_values", {})

            stage_val = attrs.get("stage", [{}])
            stage = stage_val[0].get("status", {}).get("title", "") if stage_val else ""

            cold_since = None
            cold_since_vals = attrs.get("cold_since", [])
            if cold_since_vals:
                raw_date = cold_since_vals[0].get("value")
                if raw_date:
                    cold_since = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))

            return PipelineEntry(
                entry_id=entry_id,
                record_id=record_id,
                pipeline=pipeline,
                stage=stage,
                cold_since=cold_since,
            )
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("Could not parse entry: %s — %s", raw.get("id"), exc)
            return None

    # ------------------------------------------------------------------
    # Company record
    # ------------------------------------------------------------------

    async def get_company_record(self, record_id: str) -> AttioRecord:
        data = await self._request("GET", f"/objects/companies/records/{record_id}")
        return self._parse_record(record_id, data.get("data", {}))

    async def get_full_context(self, record_id: str) -> AttioRecord:
        record = await self.get_company_record(record_id)
        notes = await self.get_notes(record_id)
        record.notes = notes
        return record

    def _parse_record(self, record_id: str, data: dict) -> AttioRecord:
        attrs = data.get("values", {})

        def first_val(key, subkey="value"):
            vals = attrs.get(key, [])
            return vals[0].get(subkey) if vals else None

        company_name = first_val("name") or record_id

        def parse_dt(key) -> Optional[datetime]:
            val = first_val(key)
            if val:
                try:
                    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                except ValueError:
                    return None
            return None

        last_email = parse_dt("last_email_interaction")
        last_calendar = parse_dt("last_calendar_interaction")

        # Pull associated contacts
        contacts = []
        for person in attrs.get("team", []):
            person_data = person.get("target_record", {}).get("values", {})
            name_vals = person_data.get("name", [{}])
            name = name_vals[0].get("full_name", "") if name_vals else ""
            email_vals = person_data.get("primary_email_address", [{}])
            email = email_vals[0].get("email_address") if email_vals else None
            title_vals = person_data.get("job_title", [{}])
            title = title_vals[0].get("value") if title_vals else None
            if name:
                contacts.append(AttioContact(name=name, email=email, title=title))

        return AttioRecord(
            record_id=record_id,
            company_name=company_name,
            last_email_interaction=last_email,
            last_calendar_interaction=last_calendar,
            contacts=contacts,
            raw=data,
        )

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    async def get_notes(self, record_id: str) -> list[dict]:
        data = await self._request(
            "GET",
            "/notes",
            params={
                "parent_object": "companies",
                "parent_record_id": record_id,
                "limit": 20,
            },
        )
        return data.get("data", [])

    async def add_note(self, record_id: str, title: str, content: str):
        await self._request(
            "POST",
            "/notes",
            json={
                "data": {
                    "parent_object": "companies",
                    "parent_record_id": record_id,
                    "title": title,
                    "content": content,
                }
            },
        )
        logger.info("Added note to record %s: %s", record_id, title)

    # ------------------------------------------------------------------
    # Stage updates
    # ------------------------------------------------------------------

    async def update_stage(self, entry: PipelineEntry, stage_title: str):
        await self._request(
            "PATCH",
            f"/lists/{entry.pipeline}/entries/{entry.entry_id}",
            json={"data": {"stage": {"status": stage_title}}},
        )
        logger.info(
            "Updated %s (entry %s) → %s",
            entry.record_id, entry.entry_id, stage_title,
        )
