"""
Gmail API client using OAuth2.
Supports reply-threading: always looks for an existing thread with the
contact before sending, and replies into it when found.
Token is loaded from GCP Secret Manager and refreshed automatically.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import config

logger = logging.getLogger(__name__)

SENDER = config.GMAIL_SENDER
AGENT_HEADER_NAME = "X-Plannery-Agent"
AGENT_HEADER_VALUE = "pipeline-followup"


@dataclass
class ThreadContext:
    """Metadata about an existing Gmail thread to reply into."""
    thread_id: str
    last_message_id: str        # RFC 2822 Message-Id header of the last message
    last_sender_name: str       # Display name of the last person who replied
    last_sender_email: str
    all_participants: list[str] = field(default_factory=list)  # all To/CC emails


def _build_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_json = config.gmail_oauth_token()
    creds_data = json.loads(token_json)
    creds = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=creds_data.get("scopes", ["https://mail.google.com/"]),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _update_token_secret(creds)
    return build("gmail", "v1", credentials=creds)


def _update_token_secret(creds):
    try:
        from google.cloud import secretmanager
        updated = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else [],
        }
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{config.GCP_PROJECT}/secrets/gmail-oauth-token"
        client.add_secret_version(
            request={"parent": parent, "payload": {"data": json.dumps(updated).encode()}}
        )
        logger.info("Gmail OAuth token refreshed and stored in Secret Manager")
    except Exception as exc:
        logger.warning("Could not update token in Secret Manager: %s", exc)


def _header_value(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _parse_address(addr_str: str) -> tuple[str, str]:
    """Parse 'Display Name <email>' → (name, email). Falls back gracefully."""
    addr_str = addr_str.strip()
    if "<" in addr_str and ">" in addr_str:
        name = addr_str[:addr_str.index("<")].strip().strip('"')
        email = addr_str[addr_str.index("<") + 1:addr_str.index(">")].strip()
        return name, email
    return "", addr_str


class GmailClient:
    def __init__(self, test_mode: bool = False):
        self._service = None
        self._test_mode = test_mode

    def _get_service(self):
        if self._service is None:
            self._service = _build_service()
        return self._service

    # ------------------------------------------------------------------
    # Thread discovery
    # ------------------------------------------------------------------

    async def find_existing_thread(self, contact_emails: list[str]) -> Optional[ThreadContext]:
        """
        Search Gmail for the most recent thread involving any of the contact
        emails. Returns thread metadata for reply threading, or None if no
        prior thread exists.
        """
        if not contact_emails:
            return None

        service = self._get_service()
        query_parts = [f"(from:{e} OR to:{e})" for e in contact_emails if e]
        query = " OR ".join(query_parts)

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: service.users().threads().list(
                    userId="me", q=query, maxResults=5
                ).execute()
            )
            threads = result.get("threads", [])
            if not threads:
                return None

            # Get the most recent thread
            thread_id = threads[0]["id"]
            thread_detail = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: service.users().threads().get(
                    userId="me", id=thread_id, format="metadata",
                    metadataHeaders=["From", "To", "Cc", "Message-Id", "Subject"]
                ).execute()
            )

            messages = thread_detail.get("messages", [])
            if not messages:
                return None

            last_msg = messages[-1]
            headers = last_msg.get("payload", {}).get("headers", [])

            last_message_id = _header_value(headers, "Message-Id")
            from_str = _header_value(headers, "From")
            last_name, last_email = _parse_address(from_str)

            # Collect all participants across the thread
            all_emails: set[str] = set()
            for msg in messages:
                for hdr_name in ("From", "To", "Cc"):
                    val = _header_value(msg.get("payload", {}).get("headers", []), hdr_name)
                    for part in val.split(","):
                        _, e = _parse_address(part)
                        if e and e.lower() != SENDER.lower():
                            all_emails.add(e)

            logger.info(
                "Found existing Gmail thread %s (%d messages) with %s",
                thread_id, len(messages), last_email,
            )
            return ThreadContext(
                thread_id=thread_id,
                last_message_id=last_message_id,
                last_sender_name=last_name,
                last_sender_email=last_email,
                all_participants=list(all_emails),
            )

        except Exception as exc:
            logger.warning("Thread search failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Send (new thread or reply)
    # ------------------------------------------------------------------

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_context: Optional[ThreadContext] = None,
        cc: Optional[list[str]] = None,
    ) -> dict:
        """
        Send a plain-text email.
        - In test_mode: recipient is always overridden to SENDER.
        - If thread_context is provided: replies into the existing Gmail thread.
        - Always BCCs SENDER for record-keeping.
        """
        if self._test_mode or not to:
            actual_to = SENDER
            cc = None  # no CC in test mode
            logger.info("Test mode — redirecting email to %s", SENDER)
        else:
            actual_to = to

        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "plain"))

        msg["From"] = SENDER
        msg["To"] = actual_to
        msg["Subject"] = subject
        msg["Bcc"] = SENDER
        msg[AGENT_HEADER_NAME] = AGENT_HEADER_VALUE

        if cc and not self._test_mode:
            msg["Cc"] = ", ".join(cc)

        # Threading headers — makes the email a reply in the existing thread
        if thread_context and thread_context.last_message_id:
            msg["In-Reply-To"] = thread_context.last_message_id
            msg["References"] = thread_context.last_message_id

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        body_payload: dict = {"raw": raw}
        if thread_context and not self._test_mode:
            body_payload["threadId"] = thread_context.thread_id

        service = self._get_service()
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: service.users().messages().send(
                userId="me", body=body_payload
            ).execute()
        )

        logger.info(
            "Email sent — to: %s, subject: %s, thread: %s, message_id: %s",
            actual_to, subject,
            thread_context.thread_id if thread_context else "new",
            result.get("id"),
        )
        return result
