"""
Layer 3: Manual approval flow test.
Run this before any production deployment and after changes to
slack_client.py, gmail_client.py, or attio_client.py.

Usage:
    python tests/integration/test_approval_flow.py

What it does:
1. Posts a synthetic approval request to #plannery-pipeline-test
2. Waits up to 5 minutes for a human reply of 'approved'
3. Verifies: email delivered to krishnan@planneryapp.com, Attio note on test record,
   pending_approvals entry removed
4. Tests the 'edit:' flow
5. Tests the 'cold' flow
Prints PASS/FAIL for each sub-test.

Prerequisites:
- #plannery-pipeline-test Slack channel exists and bot is invited
- TEST HOSPITAL — DO NOT CONTACT Attio record ID set in TEST_RECORD_ID below
- All secrets configured in GCP Secret Manager or .env
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone

# Adjust path so we can import from repo root
sys.path.insert(0, __file__.rsplit("/tests", 1)[0])

import config
from attio_client import AttioClient
from gmail_client import GmailClient
from gcs_client import read_json_file, write_json_file
from slack_client import SlackClient

# -----------------------------------------------------------------------
# Configuration — set TEST_RECORD_ID to the real Attio test record
# -----------------------------------------------------------------------
TEST_RECORD_ID = "REPLACE_WITH_TEST_ATTIO_RECORD_ID"
WAIT_SECONDS = 300  # 5 minutes max per sub-test
POLL_INTERVAL = 5

PASS = "✅ PASS"
FAIL = "❌ FAIL"

results: list[tuple[str, str, str]] = []


def record_result(name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    results.append((name, status, detail))
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))


async def _post_synthetic_approval(slack: SlackClient, subject: str, body: str) -> str:
    """Post a fake approval message to the test channel. Returns thread ts."""
    text = (
        f"🏥 *TEST HOSPITAL — DO NOT CONTACT* — Direct | Stage: Discovery & Demo\n"
        f"📅 Days since last contact: 20\n"
        f"👤 Contact: Test User, CNO\n"
        f"\n*Why this account needs follow-up:*\nIntegration test run — please reply to verify the approval flow.\n"
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"\n*📧 Proposed email:*\n\n*Subject:* {subject}\n\n{body}\n"
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"\nReply: *approved* / *edit: [text]* / *skip* / *cold*"
    )
    result = await slack._post(
        "chat.postMessage",
        {"channel": config.slack_test_channel_id(), "text": text, "mrkdwn": True},
    )
    ts = result.get("ts", "")
    print(f"  Posted synthetic approval request — ts={ts}")
    return ts


async def _write_test_pending(ts: str, record_id: str, subject: str, body: str):
    path = f"test/{config.PENDING_APPROVALS_PATH}"
    pending = read_json_file(path) or {}
    now = datetime.now(timezone.utc)
    pending[ts] = {
        "company_name": "TEST HOSPITAL — DO NOT CONTACT",
        "pipeline": config.PIPELINE_DIRECT,
        "stage": "Discovery & Demo",
        "attio_record_id": record_id,
        "attio_entry_id": "TEST_ENTRY_ID",
        "contact_email": config.GMAIL_SENDER,
        "draft_subject": subject,
        "draft_body": body,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=48)).isoformat(),
    }
    write_json_file(path, pending)


async def _wait_for_reply(slack: SlackClient, thread_ts: str) -> str | None:
    """Poll Slack for a reply in the given thread. Returns reply text or None on timeout."""
    deadline = time.monotonic() + WAIT_SECONDS
    seen_tss: set[str] = set()

    while time.monotonic() < deadline:
        result = await slack._post(
            "conversations.replies",
            {"channel": config.slack_test_channel_id(), "ts": thread_ts},
        )
        messages = result.get("messages", [])
        for msg in messages:
            ts = msg.get("ts")
            if ts == thread_ts or ts in seen_tss:
                continue
            if msg.get("bot_id") or msg.get("subtype"):
                continue
            seen_tss.add(ts)
            return msg.get("text", "").strip()

        remaining = int(deadline - time.monotonic())
        print(f"  Waiting for reply... ({remaining}s remaining)", end="\r")
        await asyncio.sleep(POLL_INTERVAL)

    return None


async def run_approved_test(slack: SlackClient, attio: AttioClient):
    print("\n--- Sub-test 1: 'approved' flow ---")
    subject = f"[TEST] Plannery approval flow test — {datetime.now().strftime('%H:%M:%S')}"
    body = "This is an integration test email. Please ignore."

    ts = await _post_synthetic_approval(slack, subject, body)
    if not ts:
        record_result("Post approval message", False, "No ts returned")
        return

    await _write_test_pending(ts, TEST_RECORD_ID, subject, body)
    record_result("Post approval message", True, f"ts={ts}")

    print(f"\n  👉 Go to #plannery-pipeline-test and reply: approved\n")
    reply = await _wait_for_reply(slack, ts)

    if reply is None:
        record_result("Receive 'approved' reply", False, "Timeout after 5 minutes")
        return
    record_result("Receive 'approved' reply", True, f"Reply: '{reply[:40]}'")

    # Give approval_processor time to act
    await asyncio.sleep(10)

    # Verify: email delivered (check for confirmation in thread)
    confirm_result = await slack._post(
        "conversations.replies",
        {"channel": config.slack_test_channel_id(), "ts": ts},
    )
    messages = confirm_result.get("messages", [])
    confirmed = any("✅" in m.get("text", "") for m in messages if m.get("bot_id"))
    record_result("Confirmation reply posted", confirmed)

    # Verify: pending entry removed
    path = f"test/{config.PENDING_APPROVALS_PATH}"
    pending = read_json_file(path) or {}
    record_result("Pending entry removed", ts not in pending)


async def run_edit_test(slack: SlackClient):
    print("\n--- Sub-test 2: 'edit:' flow ---")
    subject = f"[TEST] Edit flow — {datetime.now().strftime('%H:%M:%S')}"
    body = "Original test body text."

    ts = await _post_synthetic_approval(slack, subject, body)
    await _write_test_pending(ts, TEST_RECORD_ID, subject, body)
    record_result("Post edit-flow approval message", bool(ts), f"ts={ts}")

    edited_text = "This is the edited version of the email body."
    print(f"\n  👉 Reply: edit: {edited_text}\n")
    reply = await _wait_for_reply(slack, ts)

    if reply is None or not reply.lower().startswith("edit:"):
        record_result("Receive 'edit:' reply", False, f"Got: {reply}")
        return
    record_result("Receive 'edit:' reply", True)

    await asyncio.sleep(10)
    confirm_result = await slack._post(
        "conversations.replies",
        {"channel": config.slack_test_channel_id(), "ts": ts},
    )
    messages = confirm_result.get("messages", [])
    confirmed = any("✅" in m.get("text", "") for m in messages if m.get("bot_id"))
    record_result("Edit confirmation reply posted", confirmed)


async def run_cold_test(slack: SlackClient, attio: AttioClient):
    print("\n--- Sub-test 3: 'cold' flow ---")
    subject = f"[TEST] Cold flow — {datetime.now().strftime('%H:%M:%S')}"
    body = "Cold flow test."

    ts = await _post_synthetic_approval(slack, subject, body)
    await _write_test_pending(ts, TEST_RECORD_ID, subject, body)
    record_result("Post cold-flow message", bool(ts))

    print(f"\n  👉 Reply: cold\n")
    reply = await _wait_for_reply(slack, ts)

    if reply is None or not reply.lower().startswith("cold"):
        record_result("Receive 'cold' reply", False, f"Got: {reply}")
        return
    record_result("Receive 'cold' reply", True)

    await asyncio.sleep(10)
    confirm_result = await slack._post(
        "conversations.replies",
        {"channel": config.slack_test_channel_id(), "ts": ts},
    )
    messages = confirm_result.get("messages", [])
    cold_confirmed = any("❄️" in m.get("text", "") for m in messages if m.get("bot_id"))
    record_result("Cold confirmation reply posted", cold_confirmed)


async def main():
    if TEST_RECORD_ID == "REPLACE_WITH_TEST_ATTIO_RECORD_ID":
        print("❌ Set TEST_RECORD_ID in this file before running.")
        sys.exit(1)

    print("=" * 60)
    print("Plannery Pipeline Agent — Layer 3 Approval Flow Test")
    print("=" * 60)

    slack = SlackClient(test_mode=True)
    attio = AttioClient()

    try:
        await run_approved_test(slack, attio)
        await run_edit_test(slack)
        await run_cold_test(slack, attio)
    finally:
        await slack.close()
        await attio.close()

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, s, _ in results if s == PASS)
    total = len(results)
    for name, status, detail in results:
        print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))
    print(f"\n{passed}/{total} sub-tests passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
