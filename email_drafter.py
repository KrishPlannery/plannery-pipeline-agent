"""
Email drafter — uses the Claude API to produce a follow-up email draft.
Reads krish_email_skill.md before every run.
Returns a typed EmailDraft object parsed from Claude's JSON output.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import anthropic

import config
from attio_client import AttioRecord, PipelineEntry
from cadence_engine import FlaggedAccount
from web_researcher import ResearchResult

logger = logging.getLogger(__name__)


@dataclass
class EmailDraft:
    subject: str
    to: str
    body: str
    rationale: str
    value_props_used: list[str] = field(default_factory=list)
    research_used: bool = False


_SYSTEM_PROMPT_TEMPLATE = """You are drafting follow-up emails on behalf of Krish Gopalakrishan, founder and CEO of Plannery Inc.

ABOUT KRISH AND PLANNERY:
Plannery is a healthcare fintech company offering AI-powered financial coaching and debt consolidation lending to healthcare workers, distributed through HealthStream. Plannery is already embedded in HealthStream's hStream Benefits platform. No cost to the hospital, no IT integration required, no liability for HR.

Key proof points to draw from when relevant:
- NPS: 86 among enrolled nurses
- Zero employee complaints across all hospital activations
- NSI 2026: each 1% reduction in RN turnover saves the average hospital $295,000
- NSI 2026: cost of RN turnover is $60,090 per nurse
- 75% of healthcare professionals experience financial stress daily (Nursegrid/Plannery 2024 survey)

KRISH'S EMAIL PREFERENCES:
{skill_file_contents}

ACCOUNT CONTEXT:
- Company: {company_name}
- Pipeline: {pipeline_name}
- Stage: {stage_name}
- Days since last contact: {days_since_contact}
- Last interaction type: {last_interaction_type}
- Key contacts: {contacts}
- Recent Attio notes: {notes_summary}
- Recent web research: {research_summary}
- Cold sequence position (if Cold): {cold_week}

DRAFT RULES:
1. Never start with "I hope this finds you well" or any variant
2. Never use "just following up" or "circling back"
3. Lead with a specific, relevant hook — a news item, a data point, or a direct reference to the last conversation
4. The email must have one clear ask — not multiple asks
5. Maximum 150 words in the email body
6. Subject line must be specific — never generic like "Checking in" or "Following up"
7. If web research surfaced a relevant news item about this account, reference it naturally
8. Match the tone to the stage: warmer and more exploratory at early stages, more direct and time-aware at later stages
9. Never mention competitor products by name
10. Sign off as: Krish | Founder, Plannery | krishnan@planneryapp.com

OUTPUT FORMAT — return exactly this JSON and nothing else:
{{
  "subject": "...",
  "to": "contact email if known, else blank",
  "body": "...",
  "rationale": "one sentence explaining why this message was chosen for this account at this stage",
  "value_props_used": ["list of Plannery proof points used in the draft"],
  "research_used": true/false
}}"""

_COLD_WEEK_ADDENDUM = {
    1: "COLD WEEK 1: Lead with a new data point or Nursegrid insight. No ask for a meeting. Purely a value-add touch.",
    3: "COLD WEEK 3: Lead with the dollar model calculation specific to their hospital size. Make the inaction feel costly. One soft ask.",
    6: "COLD WEEK 6: The 'permission to close' email. Under 80 words. Create loss aversion. Direct ask: are they interested or should we stop reaching out?",
    10: "COLD WEEK 10: Move to quarterly track. Tone shifts to long-term relationship, no immediate ask.",
}


def _format_contacts(record: AttioRecord) -> str:
    if not record.contacts:
        return "Unknown"
    return "; ".join(
        f"{c.name} ({c.title or 'title unknown'}) — {c.email or 'no email'}"
        for c in record.contacts[:3]
    )


def _format_notes(record: AttioRecord) -> str:
    if not record.notes:
        return "No notes on record"
    recent = record.notes[:3]
    parts = []
    for note in recent:
        title = note.get("title", "Note")
        content = note.get("content", "")
        parts.append(f"{title}: {content[:200]}")
    return " | ".join(parts)


def _format_research(result: ResearchResult) -> str:
    if not result.recent_news:
        return "No recent news found"
    items = []
    for item in result.recent_news[:3]:
        items.append(
            f"[{item.date}] {item.headline} ({item.publication}): {item.summary}"
        )
    return "\n".join(items)


def _pipeline_display(pipeline_slug: str) -> str:
    if "healthstream" in pipeline_slug:
        return "HealthStream Channel"
    return "Direct Channel"


def _last_interaction_type(record: AttioRecord) -> str:
    email_dt = record.last_email_interaction
    cal_dt = record.last_calendar_interaction
    if email_dt and cal_dt:
        return "email" if email_dt >= cal_dt else "calendar/meeting"
    if email_dt:
        return "email"
    if cal_dt:
        return "calendar/meeting"
    return "unknown"


class EmailDrafter:

    def __init__(self, skill_manager=None):
        self._skill_manager = skill_manager
        self._client: Optional[anthropic.AsyncAnthropic] = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key())
        return self._client

    async def draft(
        self,
        account: FlaggedAccount,
        context: AttioRecord,
        research: ResearchResult,
    ) -> EmailDraft:
        skill_contents = ""
        if self._skill_manager:
            skill_contents = self._skill_manager.read()

        cold_week = account.cold_week
        cold_addendum = ""
        if account.entry.stage == "Cold" and cold_week in _COLD_WEEK_ADDENDUM:
            cold_addendum = f"\n\nCOLD SEQUENCE OVERRIDE:\n{_COLD_WEEK_ADDENDUM[cold_week]}"

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            skill_file_contents=skill_contents or "(no skill file loaded)",
            company_name=context.company_name,
            pipeline_name=_pipeline_display(account.entry.pipeline),
            stage_name=account.entry.stage,
            days_since_contact=account.days_since_contact,
            last_interaction_type=_last_interaction_type(context),
            contacts=_format_contacts(context),
            notes_summary=_format_notes(context),
            research_summary=_format_research(research),
            cold_week=cold_week or "N/A",
        ) + cold_addendum

        client = self._get_client()
        message = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Draft the follow-up email for {context.company_name}.",
                }
            ],
        )

        raw = message.content[0].text.strip()
        draft = self._parse_draft(raw, context)
        self._enforce_word_count(draft)
        logger.info(
            "Drafted email for %s — subject: %s, words: %d",
            context.company_name,
            draft.subject,
            len(draft.body.split()),
        )
        return draft

    @staticmethod
    def _parse_draft(raw: str, context: AttioRecord) -> EmailDraft:
        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(raw)
            return EmailDraft(
                subject=data.get("subject", "Follow-up"),
                to=data.get("to", ""),
                body=data.get("body", ""),
                rationale=data.get("rationale", ""),
                value_props_used=data.get("value_props_used", []),
                research_used=bool(data.get("research_used", False)),
            )
        except json.JSONDecodeError:
            logger.error("Claude returned non-JSON for %s — using raw text as body", context.company_name)
            return EmailDraft(
                subject=f"Follow-up — {context.company_name}",
                to="",
                body=raw[:1000],
                rationale="JSON parse failed — using raw response",
            )

    @staticmethod
    def _enforce_word_count(draft: EmailDraft):
        words = draft.body.split()
        if len(words) > config.MAX_EMAIL_WORDS:
            # Truncate at sentence boundary nearest to the limit
            truncated = " ".join(words[: config.MAX_EMAIL_WORDS])
            last_period = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
            if last_period > len(truncated) * 0.6:
                truncated = truncated[: last_period + 1]
            draft.body = truncated
            logger.warning(
                "Email body truncated from %d to %d words", len(words), len(draft.body.split())
            )
