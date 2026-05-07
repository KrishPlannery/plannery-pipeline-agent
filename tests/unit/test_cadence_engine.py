"""
Unit tests for cadence_engine.py.
All tests use mocked data — no API calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock

import pytest

# config stub installed by conftest.py before collection
from attio_client import AttioContact, AttioRecord, PipelineEntry
from cadence_engine import CadenceEngine, FlaggedAccount


NOW = datetime(2026, 5, 6, 10, 0, 0, tzinfo=timezone.utc)


def _make_record(
    name: str = "Test Hospital",
    days_ago: int = 10,
) -> AttioRecord:
    last_contact = NOW - timedelta(days=days_ago)
    return AttioRecord(
        record_id="rec_123",
        company_name=name,
        last_email_interaction=last_contact,
        last_calendar_interaction=None,
        contacts=[AttioContact(name="Jane Doe", email="jane@hospital.org", title="CNO")],
    )


def _make_entry(
    stage: str,
    pipeline: str = "hospital_pipeline_healthstream",
    cold_since_days: Optional[int] = None,
    record: Optional[AttioRecord] = None,
) -> PipelineEntry:
    cold_since = (NOW - timedelta(days=cold_since_days)) if cold_since_days else None
    entry = PipelineEntry(
        entry_id="entry_1",
        record_id="rec_123",
        pipeline=pipeline,
        stage=stage,
        cold_since=cold_since,
        record=record or _make_record(),
    )
    return entry


engine = CadenceEngine()


# ---------------------------------------------------------------------------
# HealthStream cadence
# ---------------------------------------------------------------------------

class TestHealthStreamCadence:

    def test_hs_flagged_not_flagged_within_7_days(self):
        entry = _make_entry("HS Flagged", record=_make_record(days_ago=5))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 0

    def test_hs_flagged_flagged_at_7_days(self):
        entry = _make_entry("HS Flagged", record=_make_record(days_ago=7))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 1

    def test_hs_demo_done_not_flagged_within_7_days(self):
        entry = _make_entry("Demo Done", record=_make_record(days_ago=6))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 0

    def test_hs_demo_done_flagged_at_7_days(self):
        entry = _make_entry("Demo Done", record=_make_record(days_ago=7))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 1

    def test_hs_demo_done_cold_escalation_at_14_days(self):
        entry = _make_entry("Demo Done", record=_make_record(days_ago=14))
        result = engine.evaluate([entry], now=NOW)
        assert entry in result.cold_escalations

    def test_hs_demo_done_cold_escalation_not_at_13_days(self):
        entry = _make_entry("Demo Done", record=_make_record(days_ago=13))
        result = engine.evaluate([entry], now=NOW)
        assert entry not in result.cold_escalations

    def test_hs_benefits_engaged_cold_at_21_days(self):
        entry = _make_entry("Benefits Engaged", record=_make_record(days_ago=21))
        result = engine.evaluate([entry], now=NOW)
        assert entry in result.cold_escalations

    def test_hs_verbal_commit_cadence_5_days(self):
        entry = _make_entry("Verbal Commit", record=_make_record(days_ago=5))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 1

    def test_hs_verbal_commit_not_flagged_at_4_days(self):
        entry = _make_entry("Verbal Commit", record=_make_record(days_ago=4))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 0

    def test_hs_enrolled_not_flagged_within_90_days(self):
        entry = _make_entry("Enrolled", record=_make_record(days_ago=60))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 0

    def test_hs_enrolled_flagged_at_90_days(self):
        entry = _make_entry("Enrolled", record=_make_record(days_ago=90))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 1


# ---------------------------------------------------------------------------
# Direct pipeline cadence
# ---------------------------------------------------------------------------

class TestDirectCadence:

    def test_qualified_lead_flagged_at_5_days(self):
        entry = _make_entry("Qualified Lead", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=5))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 1

    def test_qualified_lead_cold_at_14_days(self):
        entry = _make_entry("Qualified Lead", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=14))
        result = engine.evaluate([entry], now=NOW)
        assert entry in result.cold_escalations

    def test_discovery_demo_flagged_at_7_days(self):
        entry = _make_entry("Discovery & Demo", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=7))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 1

    def test_discovery_demo_cold_at_14_days(self):
        entry = _make_entry("Discovery & Demo", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=14))
        result = engine.evaluate([entry], now=NOW)
        assert entry in result.cold_escalations

    def test_multi_stakeholder_cadence_10_days(self):
        entry = _make_entry("Multi-Stakeholder", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=10))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 1

    def test_multi_stakeholder_cold_at_28_days(self):
        entry = _make_entry("Multi-Stakeholder", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=28))
        result = engine.evaluate([entry], now=NOW)
        assert entry in result.cold_escalations

    def test_internal_review_cadence_14_days(self):
        entry = _make_entry("Internal Review", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=14))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 1

    def test_internal_review_cold_at_35_days(self):
        entry = _make_entry("Internal Review", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=35))
        result = engine.evaluate([entry], now=NOW)
        assert entry in result.cold_escalations

    def test_contract_cadence_7_days(self):
        entry = _make_entry("Contract", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=7))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 1

    def test_enrolled_not_flagged_within_90_days(self):
        entry = _make_entry("Enrolled", pipeline="hospital_pipeline_direct", record=_make_record(days_ago=60))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 0


# ---------------------------------------------------------------------------
# Cold week calculation
# ---------------------------------------------------------------------------

class TestColdWeekCalculation:

    def test_cold_week_1_at_0_days(self):
        entry = _make_entry("Cold", cold_since_days=0)
        assert engine.get_cold_week(entry) == 1

    def test_cold_week_1_at_13_days(self):
        entry = _make_entry("Cold", cold_since_days=13)
        assert engine.get_cold_week(entry) == 1

    def test_cold_week_3_at_21_days(self):
        entry = _make_entry("Cold", cold_since_days=21)
        assert engine.get_cold_week(entry) == 3

    def test_cold_week_3_at_41_days(self):
        entry = _make_entry("Cold", cold_since_days=41)
        assert engine.get_cold_week(entry) == 3

    def test_cold_week_6_at_42_days(self):
        entry = _make_entry("Cold", cold_since_days=42)
        assert engine.get_cold_week(entry) == 6

    def test_cold_week_10_at_70_days(self):
        entry = _make_entry("Cold", cold_since_days=70)
        assert engine.get_cold_week(entry) == 10

    def test_cold_week_1_when_no_cold_since(self):
        entry = _make_entry("Cold", cold_since_days=None)
        assert engine.get_cold_week(entry) == 1


# ---------------------------------------------------------------------------
# Pending approval skip logic
# ---------------------------------------------------------------------------

class TestPendingApprovalSkip:

    def test_pending_approval_account_skipped(self):
        entry = _make_entry(
            "Multi-Stakeholder",
            pipeline="hospital_pipeline_direct",
            record=_make_record(name="Baptist Health", days_ago=30),
        )
        pending = {"some_ts": {"company_name": "Baptist Health"}}
        result = engine.evaluate([entry], pending_approvals=pending, now=NOW)
        assert len(result.flagged) == 0
        skipped_names = [entry.record.company_name for entry, _ in result.skipped if entry.record]
        assert any("Baptist Health" in name for name in skipped_names)

    def test_pending_approval_case_insensitive(self):
        entry = _make_entry(
            "Discovery & Demo",
            pipeline="hospital_pipeline_direct",
            record=_make_record(name="Mayo Clinic", days_ago=20),
        )
        pending = {"ts_1": {"company_name": "MAYO CLINIC"}}
        result = engine.evaluate([entry], pending_approvals=pending, now=NOW)
        assert len(result.flagged) == 0

    def test_non_pending_account_still_flagged(self):
        entry = _make_entry(
            "Discovery & Demo",
            pipeline="hospital_pipeline_direct",
            record=_make_record(name="Johns Hopkins", days_ago=10),
        )
        pending = {"ts_1": {"company_name": "Baptist Health"}}
        result = engine.evaluate([entry], pending_approvals=pending, now=NOW)
        assert len(result.flagged) == 1


# ---------------------------------------------------------------------------
# Days-since-contact logic
# ---------------------------------------------------------------------------

class TestDaysSinceContact:

    def test_uses_more_recent_interaction(self):
        record = AttioRecord(
            record_id="r1",
            company_name="Test",
            last_email_interaction=NOW - timedelta(days=5),
            last_calendar_interaction=NOW - timedelta(days=3),
        )
        days = engine._days_since_contact(record, NOW)
        assert days == 3

    def test_no_contact_returns_9999(self):
        record = AttioRecord(
            record_id="r1",
            company_name="Test",
            last_email_interaction=None,
            last_calendar_interaction=None,
        )
        days = engine._days_since_contact(record, NOW)
        assert days == 9999

    def test_email_only(self):
        record = AttioRecord(
            record_id="r1",
            company_name="Test",
            last_email_interaction=NOW - timedelta(days=8),
            last_calendar_interaction=None,
        )
        assert engine._days_since_contact(record, NOW) == 8


# ---------------------------------------------------------------------------
# Unknown stage handling
# ---------------------------------------------------------------------------

class TestUnknownStage:

    def test_unknown_stage_is_skipped(self):
        entry = _make_entry("Unknown Stage XYZ", record=_make_record(days_ago=30))
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 0
        assert len(result.skipped) == 1

    def test_missing_record_is_skipped(self):
        entry = PipelineEntry(
            entry_id="e1",
            record_id="r1",
            pipeline="hospital_pipeline_healthstream",
            stage="Demo Done",
            cold_since=None,
            record=None,
        )
        result = engine.evaluate([entry], now=NOW)
        assert len(result.flagged) == 0
        assert len(result.skipped) == 1
