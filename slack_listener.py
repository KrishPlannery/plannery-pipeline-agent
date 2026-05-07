"""
Cloud Run Service — always-on FastAPI app that receives Slack Events API webhooks.
Handles message replies in the approval channel and routes them to the action processor.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

from fastapi import FastAPI, HTTPException, Request, Response

import config
from approval_processor import process_approval

logger = logging.getLogger(__name__)

app = FastAPI(title="Plannery Slack Listener")


# ---------------------------------------------------------------------------
# Slack request verification
# ---------------------------------------------------------------------------

def _verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verify the Slack request signature using the signing secret.
    Rejects requests older than 5 minutes.
    """
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False
    except (ValueError, TypeError):
        return False

    signing_secret = config.slack_signing_secret().encode()
    basestring = f"v0:{timestamp}:{body.decode()}".encode()
    computed = "v0=" + hmac.new(signing_secret, basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


# ---------------------------------------------------------------------------
# Event endpoint
# ---------------------------------------------------------------------------

@app.post("/slack/events")
async def slack_events(request: Request):
    body_bytes = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_signature(body_bytes, timestamp, signature):
        logger.warning("Slack signature verification failed")
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(body_bytes)

    # URL verification handshake
    if payload.get("type") == "url_verification":
        return Response(
            content=json.dumps({"challenge": payload["challenge"]}),
            media_type="application/json",
        )

    if payload.get("type") != "event_callback":
        return Response(content="{}", media_type="application/json")

    event = payload.get("event", {})
    event_type = event.get("type", "")

    # Only handle messages in the approval channel (not bot's own messages)
    if event_type != "message":
        return Response(content="{}", media_type="application/json")

    # Ignore bot messages and message edits/deletes
    if event.get("subtype") or event.get("bot_id"):
        return Response(content="{}", media_type="application/json")

    channel_id = event.get("channel", "")
    approval_channel = config.slack_channel_id()
    if channel_id != approval_channel:
        return Response(content="{}", media_type="application/json")

    thread_ts = event.get("thread_ts")
    message_ts = event.get("ts")
    text = event.get("text", "").strip()
    user_id = event.get("user", "")

    # Only process threaded replies (replies to an approval post)
    if not thread_ts or thread_ts == message_ts:
        return Response(content="{}", media_type="application/json")

    logger.info(
        "Slack reply in thread %s from user %s: '%s...'",
        thread_ts, user_id, text[:50],
    )

    # Hand off to approval processor (non-blocking — respond to Slack immediately)
    import asyncio
    asyncio.create_task(process_approval(thread_ts, text, user_id))

    return Response(content="{}", media_type="application/json")


@app.get("/health")
async def health():
    return {"status": "ok"}
