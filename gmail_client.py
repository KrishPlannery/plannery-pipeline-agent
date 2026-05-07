"""
Gmail API client using OAuth2.
Token JSON is loaded from GCP Secret Manager and refreshed automatically.
All sends are plain text, always BCC Krish, never send without explicit approval.
"""

from __future__ import annotations

import base64
import json
import logging
from email.mime.text import MIMEText
from typing import Optional

import config

logger = logging.getLogger(__name__)

SENDER = config.GMAIL_SENDER
AGENT_HEADER = "X-Plannery-Agent: pipeline-followup"


def _build_service():
    """Build Gmail API service from OAuth2 token stored in Secret Manager."""
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
        # Persist refreshed token back to Secret Manager
        _update_token_secret(creds)

    return build("gmail", "v1", credentials=creds)


def _update_token_secret(creds):
    """Write refreshed token back to Secret Manager so next run uses fresh credentials."""
    try:
        from google.cloud import secretmanager
        import json as _json

        updated = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else [],
        }
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{config.GCP_PROJECT}/secrets/plannery/gmail-oauth-token"
        client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": _json.dumps(updated).encode()},
            }
        )
        logger.info("Gmail OAuth token refreshed and written to Secret Manager")
    except Exception as exc:
        logger.warning("Could not update refreshed token in Secret Manager: %s", exc)


class GmailClient:
    def __init__(self, test_mode: bool = False):
        self._service = None
        self._test_mode = test_mode

    def _get_service(self):
        if self._service is None:
            self._service = _build_service()
        return self._service

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to: Optional[str] = None,
    ):
        """
        Send a plain-text email from SENDER.
        In test_mode, overrides recipient to SENDER (Krish only).
        Always BCCs SENDER for record-keeping.
        """
        if self._test_mode or not to:
            actual_to = SENDER
            logger.info("Test mode or no recipient — redirecting email to %s", SENDER)
        else:
            actual_to = to

        message = MIMEText(body, "plain")
        message["to"] = actual_to
        message["from"] = SENDER
        message["subject"] = subject
        message["bcc"] = SENDER
        message[AGENT_HEADER.split(":")[0]] = AGENT_HEADER.split(":")[1].strip()

        if reply_to:
            message["reply-to"] = reply_to

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service = self._get_service()

        # Gmail API is synchronous — run in thread pool to avoid blocking event loop
        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute(),
        )

        logger.info(
            "Email sent — to: %s, subject: %s, message_id: %s",
            actual_to, subject, result.get("id"),
        )
        return result
