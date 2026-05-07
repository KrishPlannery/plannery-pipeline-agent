"""
Slack client — posts approval requests to #plannery-pipeline and handles
thread replies, 48-hour timeout reminders, and DMs to Krish.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp

import config
from cadence_engine import FlaggedAccount
from email_drafter import EmailDraft
from web_researcher import ResearchResult

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"
TIMEOUT_HOURS = config.APPROVAL_TIMEOUT_HOURS


class SlackClient:
    def __init__(self, test_mode: bool = False):
        self._token: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._test_mode = test_mode

    def _channel(self) -> str:
        if self._test_mode:
            return config.slack_test_channel_id()
        return config.slack_channel_id()

    def _headers(self) -> dict:
        if self._token is None:
            self._token = config.slack_bot_token()
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

    async def _post(self, endpoint: str, payload: dict) -> dict:
        session = await self._session_get()
        async with session.post(
            f"{SLACK_API}/{endpoint}",
            json=payload,
            headers=self._headers(),
        ) as resp:
            data = await resp.json()
            if not data.get("ok"):
                logger.error("Slack %s error: %s", endpoint, data.get("error"))
            return data

    # ------------------------------------------------------------------
    # Post approval request
    # ------------------------------------------------------------------

    async def post_for_approval(
        self,
        account: FlaggedAccount,
        draft: EmailDraft,
        research: ResearchResult,
    ) -> str:
        """Post the approval message to the channel. Returns message timestamp."""
        contact_display = "Unknown contact"
        if account.record and account.record.contacts:
            c = account.record.contacts[0]
            parts = [c.name]
            if c.title:
                parts.append(c.title)
            contact_display = ", ".join(parts)

        pipeline_display = (
            "HealthStream" if "healthstream" in account.entry.pipeline else "Direct"
        )

        research_section = (
            research.recent_news[0].headline
            if research.recent_news
            else "No recent news found"
        )

        # Thread and CC context
        thread_line = (
            f"🧵 Replying into existing thread"
            if draft.thread_context
            else "✉️ New thread"
        )
        cc_line = f"CC: {', '.join(draft.cc)}" if draft.cc else ""

        text = (
            f"🏥 *{account.record.company_name}* — {pipeline_display} | Stage: {account.entry.stage}\n"
            f"📅 Days since last contact: {account.days_since_contact}\n"
            f"👤 Contact: {contact_display}\n"
            f"\n*Why this account needs follow-up:*\n{account.follow_up_reason}\n"
            f"\n*Recent context:*\n{research_section}\n"
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"\n*📧 Proposed email:* {thread_line}\n"
            + (f"*CC:* {cc_line}\n" if cc_line else "")
            + f"\n*Subject:* {draft.subject}\n"
            f"\n{draft.body}\n"
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"\nReply to this message with:\n"
            f"• *approved* → sends immediately via Gmail\n"
            f"• *edit: [your revised version]* → sends your version via Gmail\n"
            f"• *skip* → skips this account tonight\n"
            f"• *cold* → moves account to Cold stage in Attio"
        )

        result = await self._post(
            "chat.postMessage",
            {"channel": self._channel(), "text": text, "mrkdwn": True},
        )

        ts = result.get("ts", "")
        logger.info(
            "Posted approval request for %s — ts=%s",
            account.record.company_name, ts,
        )
        return ts

    # ------------------------------------------------------------------
    # Thread replies
    # ------------------------------------------------------------------

    async def post_thread_reply(self, thread_ts: str, text: str) -> str:
        result = await self._post(
            "chat.postMessage",
            {
                "channel": self._channel(),
                "thread_ts": thread_ts,
                "text": text,
            },
        )
        return result.get("ts", "")

    async def post_to_test_channel(self, text: str) -> dict:
        return await self._post(
            "chat.postMessage",
            {"channel": config.slack_test_channel_id(), "text": text},
        )

    # ------------------------------------------------------------------
    # DM to Krish (error alerts)
    # ------------------------------------------------------------------

    async def send_dm(self, user_id: str, text: str):
        # Open DM channel first
        result = await self._post("conversations.open", {"users": user_id})
        channel_id = result.get("channel", {}).get("id")
        if not channel_id:
            logger.error("Could not open DM with user %s", user_id)
            return
        await self._post("chat.postMessage", {"channel": channel_id, "text": text})
        logger.info("DM sent to %s", user_id)

    # ------------------------------------------------------------------
    # Pending approval timeout check
    # ------------------------------------------------------------------

    async def check_pending_approvals(self):
        """
        Called at the start of each nightly run. Posts a reminder for any
        approval that has been pending over 48 hours without a reply.
        """
        from gcs_client import read_json_file

        pending = read_json_file(config.PENDING_APPROVALS_PATH)
        if not pending:
            return

        now = datetime.now(timezone.utc)
        for ts, record in list(pending.items()):
            expires_at_raw = record.get("expires_at")
            if not expires_at_raw:
                continue
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            if now >= expires_at:
                logger.info(
                    "Reminder: approval for %s has been pending > 48h",
                    record.get("company_name"),
                )
                await self.post_thread_reply(
                    ts,
                    "⏰ This follow-up is still pending your approval. Reply approved, edit, skip, or cold.",
                )
