"""
Handles the approval/edit/skip/cold commands that arrive from Slack.
Called by slack_listener.py as a background task.
This module owns the approval state machine.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import config
from gcs_client import read_json_file, write_json_file

logger = logging.getLogger(__name__)


async def process_approval(thread_ts: str, text: str, user_id: str):
    """
    Parse Krish's reply and execute the corresponding action.
    thread_ts is the original approval message's timestamp (used as the key
    in pending_approvals.json).
    """
    from slack_client import SlackClient
    from gmail_client import GmailClient
    from attio_client import AttioClient, PipelineEntry
    from skill_manager import SkillManager

    pending = read_json_file(config.PENDING_APPROVALS_PATH)
    if thread_ts not in pending:
        logger.debug("Thread %s not in pending approvals — ignoring", thread_ts)
        return

    record = pending[thread_ts]
    slack = SlackClient()
    gmail = GmailClient()
    attio = AttioClient()
    skill = SkillManager()

    cmd = text.strip().lower()

    try:
        if cmd.startswith("approved"):
            await _handle_approved(
                thread_ts, record, slack, gmail, attio, skill, edited_body=None
            )

        elif cmd.startswith("edit:"):
            edited_body = text[5:].strip()
            await _handle_approved(
                thread_ts, record, slack, gmail, attio, skill, edited_body=edited_body
            )

        elif cmd.startswith("skip"):
            await _handle_skip(thread_ts, record, slack, pending)

        elif cmd.startswith("cold"):
            await _handle_cold(thread_ts, record, slack, attio, pending)

        else:
            logger.debug("Unrecognised command '%s' in thread %s", text[:40], thread_ts)

    except Exception as exc:
        logger.error("Error processing approval for thread %s: %s", thread_ts, exc, exc_info=True)
        try:
            await slack.post_thread_reply(
                thread_ts,
                f"⚠️ Error processing your reply: {exc}. Check Cloud Logging.",
            )
        except Exception:
            pass
    finally:
        await attio.close()


async def _handle_approved(
    thread_ts, record, slack, gmail, attio, skill, edited_body
):
    from gcs_client import read_json_file, write_json_file
    from gmail_client import ThreadContext

    pending = read_json_file(config.PENDING_APPROVALS_PATH)
    subject = record["draft_subject"]
    body = edited_body if edited_body else record["draft_body"]
    to_email = record["contact_email"]
    cc = record.get("draft_cc") or []

    # Reconstruct thread context if we have one
    thread_context = None
    if record.get("gmail_thread_id") and record.get("gmail_last_message_id"):
        thread_context = ThreadContext(
            thread_id=record["gmail_thread_id"],
            last_message_id=record["gmail_last_message_id"],
            last_sender_name="",
            last_sender_email=to_email,
        )

    await gmail.send_email(
        to=to_email,
        subject=subject,
        body=body,
        thread_context=thread_context,
        cc=cc,
    )

    ts_now = datetime.now(timezone.utc).isoformat()
    await attio.add_note(
        record_id=record["attio_record_id"],
        title=f"Follow-up email sent — {ts_now[:10]}",
        content=f"Subject: {subject}\n\n{body}",
    )

    action = "edited" if edited_body else "approved"
    skill.update_from_approval(
        draft_subject=record["draft_subject"],
        draft_body=record["draft_body"],
        edited_body=edited_body,
        action=action,
        company_name=record["company_name"],
        stage=record["stage"],
    )

    confirmation = (
        f"✅ Email sent to {to_email or record['company_name']} at {ts_now[:19]} UTC | Attio note added"
    )
    await slack.post_thread_reply(thread_ts, confirmation)

    del pending[thread_ts]
    write_json_file(config.PENDING_APPROVALS_PATH, pending)
    logger.info("Approval processed for %s", record["company_name"])


async def _handle_skip(thread_ts, record, slack, pending):
    from gcs_client import write_json_file

    await slack.post_thread_reply(
        thread_ts,
        f"⏭️ {record['company_name']} skipped tonight. No email sent, no Attio update.",
    )
    del pending[thread_ts]
    write_json_file(config.PENDING_APPROVALS_PATH, pending)
    logger.info("Skipped %s", record["company_name"])


async def _handle_cold(thread_ts, record, slack, attio, pending):
    from gcs_client import write_json_file
    from attio_client import PipelineEntry

    entry = PipelineEntry(
        entry_id=record["attio_entry_id"],
        record_id=record["attio_record_id"],
        pipeline=record["pipeline"],
        stage=record["stage"],
        cold_since=None,
    )
    await attio.update_stage(entry, "Cold")

    await slack.post_thread_reply(
        thread_ts,
        f"❄️ {record['company_name']} moved to Cold in Attio",
    )
    del pending[thread_ts]
    write_json_file(config.PENDING_APPROVALS_PATH, pending)
    logger.info("Moved %s to Cold", record["company_name"])
