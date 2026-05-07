"""
Unit tests for skill_manager.py.
Tests read/write via mocked GCS and summarization trigger logic.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if "config" not in sys.modules:
    config_stub = types.ModuleType("config")
    sys.modules["config"] = config_stub

cfg = sys.modules["config"]
cfg.SKILL_FILE_PATH = "krish_email_skill.md"
cfg.SKILL_FILE_MAX_LINES = 500
cfg.CLAUDE_MODEL = "claude-sonnet-4-20250514"
cfg.anthropic_api_key = lambda: "sk-ant-test"

# Stub gcs_client before importing skill_manager
gcs_stub = types.ModuleType("gcs_client")
_gcs_store = {}
gcs_stub.read_state_file = lambda path: _gcs_store.get(path, "")
gcs_stub.write_state_file = lambda path, content: _gcs_store.update({path: content})
sys.modules["gcs_client"] = gcs_stub


class TestSkillManagerReadWrite:

    def setup_method(self):
        _gcs_store.clear()

    def test_read_returns_empty_when_no_file(self):
        from skill_manager import SkillManager
        sm = SkillManager()
        assert sm.read() == ""

    def test_write_and_read_roundtrip(self):
        from skill_manager import SkillManager
        sm = SkillManager()
        content = "# Skill File\n## Version: 1\n- Short emails"
        sm.write(content)
        assert sm.read() == content


class TestSkillManagerSummarization:

    def setup_method(self):
        _gcs_store.clear()

    @pytest.mark.asyncio
    async def test_no_summarization_when_under_limit(self):
        from skill_manager import SkillManager
        sm = SkillManager()
        short_content = "\n".join(["line"] * 100)
        sm.write(short_content)

        with patch.object(sm, "_summarize", new_callable=AsyncMock) as mock_sum:
            await sm.summarize_if_needed()
            mock_sum.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarization_triggered_when_over_500_lines(self):
        from skill_manager import SkillManager
        sm = SkillManager()
        long_content = "\n".join(["preference line"] * 501)
        sm.write(long_content)

        condensed = "# Skill File\n## Condensed version\n- Short emails"

        with patch.object(sm, "_summarize", new_callable=AsyncMock, return_value=condensed) as mock_sum:
            await sm.summarize_if_needed()
            mock_sum.assert_called_once()
            assert sm.read() == condensed

    @pytest.mark.asyncio
    async def test_summarization_at_exactly_500_lines_not_triggered(self):
        from skill_manager import SkillManager
        sm = SkillManager()
        exact_content = "\n".join(["preference line"] * 500)
        sm.write(exact_content)

        with patch.object(sm, "_summarize", new_callable=AsyncMock) as mock_sum:
            await sm.summarize_if_needed()
            mock_sum.assert_not_called()


class TestSkillManagerUpdate:

    def setup_method(self):
        _gcs_store.clear()
        _gcs_store["krish_email_skill.md"] = "# Skill File\n## Version: 1\n"

    def test_update_on_approved_appends_note(self):
        from skill_manager import SkillManager
        sm = SkillManager()
        sm.update_from_approval(
            draft_subject="Test subject",
            draft_body="Here is a relevant data point about your workforce...",
            edited_body=None,
            action="approved",
            company_name="Mayo Clinic",
            stage="Demo Done",
        )
        updated = sm.read()
        assert "Approved draft" in updated
        assert "Mayo Clinic" in updated

    def test_update_on_edited_appends_delta(self):
        from skill_manager import SkillManager
        sm = SkillManager()
        sm.update_from_approval(
            draft_subject="Test subject",
            draft_body="Original opening with some words here.",
            edited_body="Completely different opening paragraph.",
            action="edited",
            company_name="Johns Hopkins",
            stage="Contract",
        )
        updated = sm.read()
        assert "Edited draft" in updated
        assert "Johns Hopkins" in updated

    def test_skip_does_not_update_file(self):
        from skill_manager import SkillManager
        sm = SkillManager()
        original = sm.read()
        sm.update_from_approval(
            draft_subject="Test",
            draft_body="Body",
            edited_body=None,
            action="skipped",
            company_name="Test Hospital",
            stage="HS Flagged",
        )
        assert sm.read() == original
