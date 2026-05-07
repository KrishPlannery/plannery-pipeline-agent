"""
Plannery Pipeline Intelligence Agent — nightly orchestrator.

Normal run:   python main.py
Test mode:    python main.py --test-mode [--account-id <attio_record_id>]

In test mode:
  - Attio reads are real
  - Web research is real
  - Email drafted for real using skill file
  - Slack posts go to #plannery-pipeline-test
  - Gmail send intercepted — recipient overridden to krishnan@planneryapp.com
  - Attio stage and notes are NOT updated
  - State written under test/ prefix in GCS
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

import config
from attio_client import AttioClient, PipelineEntry
from cadence_engine import CadenceEngine, FlaggedAccount
from email_drafter import EmailDrafter
from gcs_client import read_json_file, write_json_file
from skill_manager import SkillManager
from slack_client import SlackClient
from web_researcher import WebResearcher

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging(test_mode: bool = False):
    level = logging.DEBUG if test_mode else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        handlers=handlers,
    )


def log(msg: str):
    logging.getLogger("main").info(msg)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

async def smoke_test(attio: AttioClient, slack: SlackClient) -> bool:
    checks: list[tuple[str, bool, str]] = []

    try:
        result = await attio.get_pipeline_entries(config.PIPELINE_HEALTHSTREAM)
        checks.append(("Attio API", True, f"{len(result)} entries returned"))
    except Exception as e:
        checks.append(("Attio API", False, str(e)))

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key())
        msg = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Reply with the word OK only."}],
        )
        reply = msg.content[0].text
        checks.append(("Claude API", "OK" in reply.upper(), reply[:50]))
    except Exception as e:
        checks.append(("Claude API", False, str(e)))

    try:
        result = await slack.post_to_test_channel("🔍 Smoke test ping")
        checks.append(("Slack API", result.get("ok", False), "message posted"))
    except Exception as e:
        checks.append(("Slack API", False, str(e)))

    try:
        val = config.get_secret("plannery/attio-api-key")
        checks.append(("Secret Manager", len(val) > 0, "secret accessible"))
    except Exception as e:
        checks.append(("Secret Manager", False, str(e)))

    try:
        from gcs_client import read_state_file
        read_state_file(config.SKILL_FILE_PATH)
        checks.append(("Cloud Storage", True, "bucket accessible"))
    except Exception as e:
        checks.append(("Cloud Storage", False, str(e)))

    all_passed = all(c[1] for c in checks)

    if not all_passed:
        failed = [c for c in checks if not c[1]]
        msg = "⚠️ Pipeline agent smoke test FAILED\n"
        for name, _, error in failed:
            msg += f"• {name}: {error}\n"
        msg += "Nightly run aborted. Check Cloud Logging."
        try:
            await slack.send_dm(config.slack_dm_user_id(), msg)
        except Exception as dm_err:
            log(f"Could not send failure DM: {dm_err}")

    for name, passed, detail in checks:
        log(f"Smoke test [{name}]: {'PASS' if passed else 'FAIL'} — {detail}")

    return all_passed


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _pending_path(test_mode: bool) -> str:
    if test_mode:
        return f"test/{config.PENDING_APPROVALS_PATH}"
    return config.PENDING_APPROVALS_PATH


def _add_pending(
    ts: str,
    account: FlaggedAccount,
    draft,
    test_mode: bool,
):
    from datetime import timedelta
    path = _pending_path(test_mode)
    pending = read_json_file(path) or {}
    now = datetime.now(timezone.utc)
    contact_email = ""
    if account.record and account.record.contacts:
        contact_email = account.record.contacts[0].email or ""

    pending[ts] = {
        "company_name": account.record.company_name,
        "pipeline": account.entry.pipeline,
        "stage": account.entry.stage,
        "attio_record_id": account.entry.record_id,
        "attio_entry_id": account.entry.entry_id,
        "contact_email": contact_email,
        "draft_subject": draft.subject,
        "draft_body": draft.body,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=config.APPROVAL_TIMEOUT_HOURS)).isoformat(),
    }
    write_json_file(path, pending)


# ---------------------------------------------------------------------------
# Main nightly run
# ---------------------------------------------------------------------------

async def nightly_run(
    test_mode: bool = False,
    account_id: str | None = None,
):
    log(f"=== Plannery Pipeline Agent — nightly run started (test_mode={test_mode}) ===")

    attio = AttioClient()
    slack = SlackClient(test_mode=test_mode)
    skill = SkillManager()
    researcher = WebResearcher()
    drafter = EmailDrafter(skill_manager=skill)
    cadence = CadenceEngine()

    # Step 1: Smoke test (skip in test mode to avoid redundant pings)
    if not test_mode:
        passed = await smoke_test(attio, slack)
        if not passed:
            log("Smoke test failed — aborting nightly run")
            return

    # Step 2: Summarize skill file if needed
    try:
        await skill.summarize_if_needed()
    except Exception as e:
        log(f"Skill summarization failed (non-fatal): {e}")

    # Step 3: Check pending approvals for timeout reminders
    try:
        await slack.check_pending_approvals()
    except Exception as e:
        log(f"Pending approval check failed (non-fatal): {e}")

    # Step 4: Pull all active deals
    try:
        if account_id:
            # Test mode: single account
            log(f"Test mode: pulling single account {account_id}")
            record = await attio.get_full_context(account_id)
            # Create a synthetic entry for this record
            hs_entries = await attio.get_pipeline_entries(config.PIPELINE_HEALTHSTREAM)
            direct_entries = await attio.get_pipeline_entries(config.PIPELINE_DIRECT)
            all_entries = hs_entries + direct_entries
            target_entries = [e for e in all_entries if e.record_id == account_id]
            if not target_entries:
                log(f"Account {account_id} not found in any pipeline — aborting")
                return
            for entry in target_entries:
                entry.record = record
            all_deals = target_entries
        else:
            hs_deals = await attio.get_pipeline_entries(config.PIPELINE_HEALTHSTREAM)
            direct_deals = await attio.get_pipeline_entries(config.PIPELINE_DIRECT)

            # Attach company records
            all_entries = hs_deals + direct_deals
            log(f"Fetching company records for {len(all_entries)} entries...")
            for entry in all_entries:
                try:
                    entry.record = await attio.get_full_context(entry.record_id)
                except Exception as e:
                    log(f"Could not fetch record {entry.record_id}: {e}")
            all_deals = all_entries

    except Exception as e:
        log(f"FATAL: Could not fetch pipeline data from Attio: {e}")
        try:
            await slack.send_dm(
                config.slack_dm_user_id(),
                f"⚠️ Pipeline agent: Attio API down. Nightly run aborted.\n{e}",
            )
        except Exception:
            pass
        return

    # Step 5: Run cadence engine
    pending = read_json_file(_pending_path(test_mode)) or {}
    result = cadence.evaluate(all_deals, pending_approvals=pending)
    log(f"{len(result.flagged)} accounts flagged for follow-up tonight")

    # Step 6: Research, draft, post to Slack
    for account in result.flagged:
        try:
            research = await researcher.research(
                company_name=account.record.company_name,
                stage=account.entry.stage,
                notes_summary=" ".join(
                    n.get("title", "") for n in (account.record.notes or [])[:3]
                ),
            )

            draft = await drafter.draft(account, account.record, research)

            ts = await slack.post_for_approval(account, draft, research)
            _add_pending(ts, account, draft, test_mode)

            log(f"Posted approval for {account.record.company_name} — ts={ts}")
            await asyncio.sleep(config.INTER_ACCOUNT_SLACK_DELAY)

        except Exception as e:
            log(f"ERROR processing {account.record.company_name}: {e}")
            continue

    # Step 7: Cold escalations (skip Attio writes in test mode)
    for entry in result.cold_escalations:
        company = entry.record.company_name if entry.record else entry.record_id
        if test_mode:
            log(f"TEST MODE — would move {company} to Cold (skipped)")
            continue
        try:
            await attio.update_stage(entry, "Cold")
            log(f"Moved {company} to Cold")
        except Exception as e:
            log(f"Could not move {company} to Cold: {e}")

    await attio.close()
    await slack.close()
    await researcher.close()

    log(
        f"=== Nightly run complete. {len(result.flagged)} accounts processed, "
        f"{len(result.cold_escalations)} cold escalations ==="
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plannery Pipeline Agent")
    parser.add_argument("--test-mode", action="store_true", help="Run in test mode")
    parser.add_argument("--account-id", type=str, default=None, help="Limit to single Attio record ID")
    args = parser.parse_args()

    _setup_logging(test_mode=args.test_mode)
    asyncio.run(nightly_run(test_mode=args.test_mode, account_id=args.account_id))
