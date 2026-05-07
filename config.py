"""
Runtime configuration — all secrets loaded from GCP Secret Manager.
Local .env fallback is supported for development only (never in production).
"""

import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

GCP_PROJECT = "plannery-agents"
GCS_BUCKET = "plannery-agent-state"

_SECRET_PREFIX = "plannery"

_secret_client = None


def _get_secret_client():
    global _secret_client
    if _secret_client is None:
        from google.cloud import secretmanager
        _secret_client = secretmanager.SecretManagerServiceClient()
    return _secret_client


@lru_cache(maxsize=None)
def get_secret(secret_id: str) -> str:
    """
    Load a secret from GCP Secret Manager.
    Falls back to environment variable of the same name (uppercase, dashes → underscores)
    for local dev.
    """
    env_key = secret_id.replace("-", "_").replace("/", "_").upper()
    # Strip the prefix for the env var lookup (plannery_attio_api_key → ATTIO_API_KEY)
    if env_key.startswith(f"{_SECRET_PREFIX.upper()}_"):
        env_key = env_key[len(_SECRET_PREFIX) + 1:]

    env_val = os.environ.get(env_key)
    if env_val:
        logger.debug("Secret %s loaded from environment", secret_id)
        return env_val

    try:
        client = _get_secret_client()
        name = f"projects/{GCP_PROJECT}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        value = response.payload.data.decode("UTF-8").strip()
        logger.debug("Secret %s loaded from Secret Manager", secret_id)
        return value
    except Exception as exc:
        raise RuntimeError(
            f"Could not load secret '{secret_id}' from Secret Manager or environment: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Typed accessors — callers import these, not get_secret() directly
# ---------------------------------------------------------------------------

def attio_api_key() -> str:
    return get_secret("plannery/attio-api-key")

def anthropic_api_key() -> str:
    return get_secret("plannery/anthropic-api-key")

def slack_bot_token() -> str:
    return get_secret("plannery/slack-bot-token")

def slack_signing_secret() -> str:
    return get_secret("plannery/slack-signing-secret")

def slack_channel_id() -> str:
    return get_secret("plannery/slack-channel-id")

def slack_test_channel_id() -> str:
    return get_secret("plannery/slack-test-channel-id")

def slack_dm_user_id() -> str:
    return get_secret("plannery/slack-dm-user-id")

def gmail_oauth_token() -> str:
    return get_secret("plannery/gmail-oauth-token")

def search_api_key() -> str:
    return get_secret("plannery/search-api-key")

def search_provider() -> str:
    return get_secret("plannery/search-provider")


# ---------------------------------------------------------------------------
# Non-secret constants
# ---------------------------------------------------------------------------

ATTIO_BASE_URL = "https://api.attio.com/v2"
SERPER_URL = "https://google.serper.dev/search"

PIPELINE_HEALTHSTREAM = "hospital_pipeline_healthstream"
PIPELINE_DIRECT = "hospital_pipeline_direct"

GMAIL_SENDER = "krishnan@planneryapp.com"
CLAUDE_MODEL = "claude-sonnet-4-20250514"

SKILL_FILE_PATH = "krish_email_skill.md"
PENDING_APPROVALS_PATH = "state/pending_approvals.json"
LOG_PATH_PREFIX = "logs"

APPROVAL_TIMEOUT_HOURS = 48
SKILL_FILE_MAX_LINES = 500
MAX_EMAIL_WORDS = 150
MAX_RESEARCH_QUERIES = 3
RESEARCH_TIMEOUT_SECONDS = 45
NEWS_RECENCY_DAYS = 90
INTER_ACCOUNT_SLACK_DELAY = 30  # seconds between Slack posts
