"""
Installs a complete config stub before any test module is collected.
This prevents Secret Manager / GCP calls during unit tests.
"""

import sys
import types


def _make_config_stub() -> types.ModuleType:
    cfg = types.ModuleType("config")

    # Constants
    cfg.ATTIO_BASE_URL = "https://api.attio.com/v2"
    cfg.SERPER_URL = "https://google.serper.dev/search"
    cfg.PIPELINE_HEALTHSTREAM = "hospital_pipeline_healthstream"
    cfg.PIPELINE_DIRECT = "hospital_pipeline_direct"
    cfg.GMAIL_SENDER = "krishnan@planneryapp.com"
    cfg.CLAUDE_MODEL = "claude-sonnet-4-20250514"
    cfg.SKILL_FILE_PATH = "krish_email_skill.md"
    cfg.PENDING_APPROVALS_PATH = "state/pending_approvals.json"
    cfg.GCS_BUCKET = "plannery-agent-state"
    cfg.GCP_PROJECT = "plannery-agents"

    cfg.APPROVAL_TIMEOUT_HOURS = 48
    cfg.SKILL_FILE_MAX_LINES = 500
    cfg.MAX_EMAIL_WORDS = 150
    cfg.MAX_RESEARCH_QUERIES = 3
    cfg.RESEARCH_TIMEOUT_SECONDS = 45
    cfg.NEWS_RECENCY_DAYS = 90
    cfg.INTER_ACCOUNT_SLACK_DELAY = 30

    # Secret accessors — return dummy values; tests should mock these
    cfg.attio_api_key = lambda: "attio-test-key"
    cfg.anthropic_api_key = lambda: "sk-ant-test"
    cfg.slack_bot_token = lambda: "xoxb-test-token"
    cfg.slack_signing_secret = lambda: "slack-signing-test"
    cfg.slack_channel_id = lambda: "C_PROD"
    cfg.slack_test_channel_id = lambda: "C_TEST"
    cfg.slack_dm_user_id = lambda: "U_KRISH"
    cfg.gmail_oauth_token = lambda: "{}"
    cfg.search_api_key = lambda: "serper-test-key"
    cfg.search_provider = lambda: "serper"
    cfg.get_secret = lambda secret_id: "test-secret-value"

    return cfg


# Stub gcs_client so tests never hit Google Cloud Storage
if "gcs_client" not in sys.modules:
    gcs_stub = types.ModuleType("gcs_client")
    _store: dict = {}
    gcs_stub.read_state_file = lambda path: _store.get(path, "")
    gcs_stub.write_state_file = lambda path, content: _store.update({path: content})
    gcs_stub.read_json_file = lambda path: {}
    gcs_stub.write_json_file = lambda path, data: None
    sys.modules["gcs_client"] = gcs_stub

# Install before any test module imports happen
if "config" not in sys.modules:
    sys.modules["config"] = _make_config_stub()
else:
    # Top up any missing attributes on an already-installed stub
    cfg = sys.modules["config"]
    stub = _make_config_stub()
    for attr in dir(stub):
        if not attr.startswith("_") and not hasattr(cfg, attr):
            setattr(cfg, attr, getattr(stub, attr))
