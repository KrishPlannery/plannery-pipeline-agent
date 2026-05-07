"""
Thin wrapper around Google Cloud Storage for reading/writing agent state files.
All state lives in gs://plannery-agent-state/
"""

import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)

_BUCKET_NAME = config.GCS_BUCKET
_gcs_client = None


def _client():
    global _gcs_client
    if _gcs_client is None:
        from google.cloud import storage
        _gcs_client = storage.Client()
    return _gcs_client


def read_state_file(filename: str) -> str:
    bucket = _client().bucket(_BUCKET_NAME)
    blob = bucket.blob(filename)
    if not blob.exists():
        logger.debug("GCS file not found: %s — returning empty string", filename)
        return ""
    content = blob.download_as_text()
    logger.debug("Read %d chars from gs://%s/%s", len(content), _BUCKET_NAME, filename)
    return content


def write_state_file(filename: str, content: str):
    bucket = _client().bucket(_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(content, content_type="text/plain")
    logger.debug("Wrote %d chars to gs://%s/%s", len(content), _BUCKET_NAME, filename)


def read_json_file(filename: str) -> Optional[dict]:
    import json
    raw = read_state_file(filename)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse JSON from %s: %s", filename, exc)
        return {}


def write_json_file(filename: str, data: dict):
    import json
    write_state_file(filename, json.dumps(data, indent=2, default=str))
