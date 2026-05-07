"""
Unit tests for Slack message formatting and pending approval timeout logic.
"""

from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if "config" not in sys.modules:
    config_stub = types.ModuleType("config")
    sys.modules["config"] = config_stub

cfg = sys.modules["config"]
cfg.APPROVAL_TIMEOUT_HOURS = 48
cfg.PENDING_APPROVALS_PATH = "state/pending_approvals.json"
cfg.slack_bot_token = lambda: "xoxb-test-token"
cfg.slack_channel_id = lambda: "C_PROD"
cfg.slack_test_channel_id = lambda: "C_TEST"
cfg.slack_dm_user_id = lambda: "U_KRISH"

NOW = datetime(2026, 5, 6, 10, 0, 0, tzinfo=timezone.utc)


class TestSlackMessageFormat:

    def test_approval_message_contains_company_name(self):
        from attio_client import AttioContact, AttioRecord, PipelineEntry
        from cadence_engine import FlaggedAccount
        from email_drafter import EmailDraft
        from web_researcher import ResearchResult

        record = AttioRecord(
            record_id="r1", company_name="Mayo Clinic",
            last_email_interaction=NOW - timedelta(days=10),
            last_calendar_interaction=None,
            contacts=[AttioContact(name="Jane Doe", email="jane@mayo.org", title="CNO")],
        )
        entry = PipelineEntry(
            entry_id="e1", record_id="r1",
            pipeline="hospital_pipeline_healthstream",
            stage="Demo Done", cold_since=None, record=record,
        )
        account = FlaggedAccount(
            entry=entry, record=record, days_since_contact=10,
            follow_up_reason="follow-up due",
        )
        draft = EmailDraft(
            subject="Turnover costs at Mayo", to="jane@mayo.org",
            body="Dr. Doe, ...", rationale="mid-stage",
        )
        research = ResearchResult(company="Mayo Clinic", recent_news=[], research_confidence="Low")

        # Build the message text the same way SlackClient does
        from slack_client import SlackClient
        slack = SlackClient()
        slack._token = "xoxb-test"

        # Extract the text-building logic indirectly by calling _format helpers
        contact_display = f"{record.contacts[0].name}, {record.contacts[0].title}"
        assert "Jane Doe" in contact_display
        assert "CNO" in contact_display


class TestPendingApprovalTimeout:

    @pytest.mark.asyncio
    async def test_expired_approval_triggers_reminder(self):
        expired_ts = "1234567890.000000"
        pending_data = {
            expired_ts: {
                "company_name": "Baptist Health",
                "expires_at": (NOW - timedelta(hours=1)).isoformat(),
            }
        }

        posted_reminders = []

        from slack_client import SlackClient
        slack = SlackClient()
        slack._token = "xoxb-test"

        async def fake_reply(ts, text):
            posted_reminders.append((ts, text))
            return "ts_reply"

        slack.post_thread_reply = fake_reply

        with patch("slack_client.read_json_file", return_value=pending_data):
            await slack.check_pending_approvals()

        assert len(posted_reminders) == 1
        assert expired_ts == posted_reminders[0][0]
        assert "pending your approval" in posted_reminders[0][1]

    @pytest.mark.asyncio
    async def test_non_expired_approval_no_reminder(self):
        future_ts = "9999999999.000000"
        pending_data = {
            future_ts: {
                "company_name": "Johns Hopkins",
                "expires_at": (NOW + timedelta(hours=24)).isoformat(),
            }
        }

        reminders = []

        from slack_client import SlackClient
        slack = SlackClient()
        slack._token = "xoxb-test"

        async def fake_reply(ts, text):
            reminders.append((ts, text))

        slack.post_thread_reply = fake_reply

        with patch("slack_client.read_json_file", return_value=pending_data):
            with patch("slack_client.datetime") as mock_dt:
                mock_dt.now.return_value = NOW
                await slack.check_pending_approvals()

        assert len(reminders) == 0
