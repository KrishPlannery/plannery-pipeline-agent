"""
Unit tests for email_drafter.py.
No real Claude API calls — all mocked.
"""

from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Config stub (reuse if already patched by cadence test, else create)
if "config" not in sys.modules:
    config_stub = types.ModuleType("config")
    config_stub.MAX_EMAIL_WORDS = 150
    config_stub.CLAUDE_MODEL = "claude-sonnet-4-20250514"
    sys.modules["config"] = config_stub
else:
    sys.modules["config"].MAX_EMAIL_WORDS = 150
    sys.modules["config"].CLAUDE_MODEL = "claude-sonnet-4-20250514"

from attio_client import AttioContact, AttioRecord, PipelineEntry
from cadence_engine import FlaggedAccount
from email_drafter import EmailDraft, EmailDrafter
from web_researcher import ResearchResult

NOW = datetime(2026, 5, 6, 10, 0, 0, tzinfo=timezone.utc)


def _make_account(stage="Demo Done", days=10, pipeline="hospital_pipeline_healthstream") -> FlaggedAccount:
    record = AttioRecord(
        record_id="rec_1",
        company_name="Baptist Health South Florida",
        last_email_interaction=NOW - timedelta(days=days),
        last_calendar_interaction=None,
        contacts=[AttioContact(name="Dr. Smith", email="smith@bap.org", title="CNO")],
        notes=[{"title": "Last call", "content": "Discussed HealthStream embed, interested"}],
    )
    entry = PipelineEntry(
        entry_id="e1",
        record_id="rec_1",
        pipeline=pipeline,
        stage=stage,
        cold_since=None,
        record=record,
    )
    return FlaggedAccount(
        entry=entry,
        record=record,
        days_since_contact=days,
        follow_up_reason="follow-up due",
    )


def _make_research() -> ResearchResult:
    from web_researcher import NewsItem
    return ResearchResult(
        company="Baptist Health South Florida",
        recent_news=[
            NewsItem(
                headline="Baptist Health launches nurse retention program",
                publication="Health News Daily",
                date="May 1, 2026",
                url="https://example.com/article",
                summary="Baptist Health announced a new initiative. The program targets RN turnover.",
            )
        ],
        research_confidence="High",
        research_notes="Research completed successfully",
    )


def _mock_draft_response() -> dict:
    return {
        "subject": "Baptist Health RN turnover — $295K per 1% saved",
        "to": "smith@bap.org",
        "body": "Dr. Smith, saw Baptist Health's new retention program launch — strong timing. "
                "Our enrolled nurses at similar systems give Plannery an NPS of 86, with zero complaints. "
                "Each 1% reduction in RN turnover saves $295K based on NSI 2026 data. "
                "Worth a 20-minute call this week? Krish | Founder, Plannery | krishnan@planneryapp.com",
        "rationale": "News hook + ROI data point appropriate for mid-stage account",
        "value_props_used": ["NPS 86", "$295K per 1% RN turnover reduction"],
        "research_used": True,
    }


class TestEmailDrafterOutput:

    @pytest.mark.asyncio
    async def test_draft_returns_email_draft(self):
        account = _make_account()
        research = _make_research()

        skill_mock = MagicMock()
        skill_mock.read.return_value = "## Email Style\n- Short emails\n"

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(_mock_draft_response()))]

        with patch("anthropic.AsyncAnthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_anthropic.return_value = mock_client

            drafter = EmailDrafter(skill_manager=skill_mock)
            drafter._client = mock_client
            draft = await drafter.draft(account, account.record, research)

        assert isinstance(draft, EmailDraft)
        assert draft.subject == "Baptist Health RN turnover — $295K per 1% saved"
        assert draft.to == "smith@bap.org"
        assert draft.research_used is True

    @pytest.mark.asyncio
    async def test_email_body_under_150_words(self):
        account = _make_account()
        research = _make_research()

        skill_mock = MagicMock()
        skill_mock.read.return_value = ""

        # Long body that must be truncated
        long_body = " ".join(["word"] * 200)
        response = _mock_draft_response()
        response["body"] = long_body

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(response))]

        with patch("anthropic.AsyncAnthropic"):
            drafter = EmailDrafter(skill_manager=skill_mock)
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            drafter._client = mock_client
            draft = await drafter.draft(account, account.record, research)

        assert len(draft.body.split()) <= 150

    def test_word_count_enforcement_truncates(self):
        draft = EmailDraft(
            subject="Test",
            to="",
            body=" ".join(["word"] * 200),
            rationale="test",
        )
        EmailDrafter._enforce_word_count(draft)
        assert len(draft.body.split()) <= 150

    def test_word_count_enforcement_leaves_short_body(self):
        body = "Short email body here."
        draft = EmailDraft(subject="Test", to="", body=body, rationale="test")
        EmailDrafter._enforce_word_count(draft)
        assert draft.body == body

    def test_parse_draft_handles_json_parse_error(self):
        record = AttioRecord(
            record_id="r1", company_name="Test Hospital",
            last_email_interaction=None, last_calendar_interaction=None,
        )
        draft = EmailDrafter._parse_draft("this is not json at all", record)
        assert draft.subject == "Follow-up — Test Hospital"
        assert "JSON parse failed" in draft.rationale

    def test_parse_draft_strips_code_fences(self):
        payload = json.dumps(_mock_draft_response())
        fenced = f"```json\n{payload}\n```"
        record = AttioRecord(
            record_id="r1", company_name="Test",
            last_email_interaction=None, last_calendar_interaction=None,
        )
        draft = EmailDrafter._parse_draft(fenced, record)
        assert draft.subject == "Baptist Health RN turnover — $295K per 1% saved"


class TestColdWeekPrompt:

    @pytest.mark.asyncio
    async def test_cold_week_1_used_in_draft(self):
        account = _make_account(stage="Cold", days=8)
        account.cold_week = 1

        research = _make_research()
        skill_mock = MagicMock()
        skill_mock.read.return_value = ""

        captured_system = {}

        async def fake_create(*args, **kwargs):
            captured_system["system"] = kwargs.get("system", "")
            mock_msg = MagicMock()
            mock_msg.content = [MagicMock(text=json.dumps(_mock_draft_response()))]
            return mock_msg

        drafter = EmailDrafter(skill_manager=skill_mock)
        mock_client = AsyncMock()
        mock_client.messages.create = fake_create
        drafter._client = mock_client

        await drafter.draft(account, account.record, research)
        assert "COLD WEEK 1" in captured_system["system"]
        assert "value-add touch" in captured_system["system"].lower() or "no ask" in captured_system["system"].lower()
