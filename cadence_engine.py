"""
Cadence engine — determines which deals need follow-up tonight and which
accounts have crossed their cold threshold.

Operates entirely on in-memory data; no API calls here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from attio_client import AttioRecord, PipelineEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cadence tables
# ---------------------------------------------------------------------------

# (follow_up_days, cold_days)
# follow_up_days: re-touch if days_since_contact >= this value
# cold_days:      escalate to Cold if days_since_contact >= this value (None = N/A)

_HS_CADENCE: dict[str, tuple[int, Optional[int]]] = {
    "HS Flagged":        (7,  21),
    "Demo Done":         (7,  14),
    "Benefits Engaged":  (7,  21),
    "Verbal Commit":     (5,  21),
    "Live":              (7,  None),
    "Enrolled":          (90, None),
    "Cold":              (7,  None),
}

_DIRECT_CADENCE: dict[str, tuple[int, Optional[int]]] = {
    "Qualified Lead":    (5,  14),
    "Discovery & Demo":  (7,  14),
    "Multi-Stakeholder": (10, 28),
    "Internal Review":   (14, 35),
    "Contract":          (7,  21),
    "Live":              (7,  None),
    "Enrolled":          (90, None),
    "Cold":              (7,  None),
}

# Stages that use 90-day cadence (already captured above but named for guard logic)
_ENROLLED_STAGES = {"Enrolled"}


def _cadence_for(pipeline: str, stage: str) -> Optional[tuple[int, Optional[int]]]:
    if "healthstream" in pipeline:
        return _HS_CADENCE.get(stage)
    return _DIRECT_CADENCE.get(stage)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FlaggedAccount:
    entry: PipelineEntry
    record: AttioRecord
    days_since_contact: int
    follow_up_reason: str
    cold_week: Optional[int] = None  # populated if stage == "Cold"


@dataclass
class CadenceResult:
    flagged: list[FlaggedAccount] = field(default_factory=list)
    cold_escalations: list[PipelineEntry] = field(default_factory=list)
    skipped: list[tuple[PipelineEntry, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main evaluator
# ---------------------------------------------------------------------------

class CadenceEngine:

    def evaluate(
        self,
        entries: list[PipelineEntry],
        pending_approvals: Optional[dict] = None,
        now: Optional[datetime] = None,
    ) -> CadenceResult:
        """
        Evaluate every pipeline entry.

        pending_approvals: dict keyed by slack_message_ts, values include
                           'company_name'. Accounts already awaiting approval
                           are skipped.
        now: override for the current time (used in tests).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        pending_companies: set[str] = set()
        if pending_approvals:
            for v in pending_approvals.values():
                name = v.get("company_name", "")
                if name:
                    pending_companies.add(name.lower())

        result = CadenceResult()

        for entry in entries:
            record = entry.record
            if record is None:
                logger.warning("Entry %s has no attached record — skipping", entry.entry_id)
                result.skipped.append((entry, "no record attached"))
                continue

            # Skip if already pending approval
            if record.company_name.lower() in pending_companies:
                reason = "pending approval in Slack"
                logger.debug("Skip %s: %s", record.company_name, reason)
                result.skipped.append((entry, reason))
                continue

            cadence = _cadence_for(entry.pipeline, entry.stage)
            if cadence is None:
                reason = f"unknown stage '{entry.stage}' in pipeline {entry.pipeline}"
                logger.warning("Skip %s: %s", record.company_name, reason)
                result.skipped.append((entry, reason))
                continue

            follow_up_days, cold_days = cadence
            days = self._days_since_contact(record, now)

            # Enrolled accounts only need quarterly check — guard already in table but be explicit
            if entry.stage in _ENROLLED_STAGES and days < 90:
                reason = f"enrolled, last contact {days}d ago (need 90)"
                logger.debug("Skip %s: %s", record.company_name, reason)
                result.skipped.append((entry, reason))
                continue

            # Check cold escalation first
            if cold_days is not None and days >= cold_days and entry.stage != "Cold":
                result.cold_escalations.append(entry)
                reason = f"cold threshold crossed ({days}d >= {cold_days}d)"
                logger.info("Cold escalation: %s — %s", record.company_name, reason)
                # Still draft a cold re-engagement email
                cold_week = self.get_cold_week(entry) if entry.stage == "Cold" else 1
                result.flagged.append(FlaggedAccount(
                    entry=entry,
                    record=record,
                    days_since_contact=days,
                    follow_up_reason=reason,
                    cold_week=cold_week,
                ))
                continue

            # Check follow-up cadence
            if days >= follow_up_days:
                cold_week = self.get_cold_week(entry) if entry.stage == "Cold" else None
                reason = f"follow-up due ({days}d since last contact, cadence {follow_up_days}d)"
                logger.info("Flag %s: %s", record.company_name, reason)
                result.flagged.append(FlaggedAccount(
                    entry=entry,
                    record=record,
                    days_since_contact=days,
                    follow_up_reason=reason,
                    cold_week=cold_week,
                ))
            else:
                reason = f"within cadence ({days}d < {follow_up_days}d)"
                logger.debug("Skip %s: %s", record.company_name, reason)
                result.skipped.append((entry, reason))

        logger.info(
            "Cadence evaluation complete: %d flagged, %d cold escalations, %d skipped",
            len(result.flagged), len(result.cold_escalations), len(result.skipped),
        )
        return result

    @staticmethod
    def _days_since_contact(record: AttioRecord, now: datetime) -> int:
        """Use the more recent of email and calendar interaction."""
        candidates = [
            t for t in (record.last_email_interaction, record.last_calendar_interaction)
            if t is not None
        ]
        if not candidates:
            # No known contact — treat as very stale
            return 9999
        latest = max(candidates)
        # Ensure both are tz-aware
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        return max(0, (now - latest).days)

    @staticmethod
    def get_cold_week(entry: PipelineEntry) -> int:
        """
        Returns which cold-sequence week (1, 3, 6, 10) the account is in
        based on how long it has been in Cold stage.
        Returns the nearest week bucket (1 if cold_since is unknown).
        """
        if entry.cold_since is None:
            return 1
        now = datetime.now(timezone.utc)
        cold_since = entry.cold_since
        if cold_since.tzinfo is None:
            cold_since = cold_since.replace(tzinfo=timezone.utc)
        days_cold = max(0, (now - cold_since).days)
        weeks_cold = days_cold // 7

        if weeks_cold < 3:
            return 1
        elif weeks_cold < 6:
            return 3
        elif weeks_cold < 10:
            return 6
        else:
            return 10
