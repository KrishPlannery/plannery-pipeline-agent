"""
Manages krish_email_skill.md in GCS.
- Reads and writes the living skill file
- Summarizes nightly if line count exceeds the threshold
- Updates preferences based on Krish's approval/edit decisions
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import anthropic

import config
from gcs_client import read_state_file, write_state_file

logger = logging.getLogger(__name__)

SKILL_PATH = config.SKILL_FILE_PATH
MAX_LINES = config.SKILL_FILE_MAX_LINES


class SkillManager:

    def read(self) -> str:
        return read_state_file(SKILL_PATH)

    def write(self, content: str):
        write_state_file(SKILL_PATH, content)

    # ------------------------------------------------------------------
    # Nightly summarization
    # ------------------------------------------------------------------

    async def summarize_if_needed(self):
        content = self.read()
        lines = content.splitlines()
        if len(lines) <= MAX_LINES:
            logger.info("Skill file is %d lines — no summarization needed", len(lines))
            return

        logger.info("Skill file is %d lines — summarizing", len(lines))
        condensed = await self._summarize(content, len(lines))
        self.write(condensed)
        new_lines = len(condensed.splitlines())
        logger.info("Skill file summarized: %d → %d lines", len(lines), new_lines)

    async def _summarize(self, content: str, line_count: int) -> str:
        client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key())

        prompt = f"""You are condensing a living skill file that captures email preferences for Krish Gopalakrishan, CEO of Plannery.

The file has grown to {line_count} lines. Condense it to under 200 lines while preserving every distinct preference, pattern, and instruction. Do not generalize away specifics. Do not lose any rule that has been explicitly stated. Merge redundant entries. Keep the most recent version of any preference that has evolved over time.

Current file:
{content}

Return only the condensed file content, starting with the header."""

        message = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    # ------------------------------------------------------------------
    # Update from approval decisions
    # ------------------------------------------------------------------

    def update_from_approval(
        self,
        draft_subject: str,
        draft_body: str,
        edited_body: Optional[str],
        action: str,
        company_name: str,
        stage: str,
    ):
        """
        Called after Krish approves, edits, or skips a draft.
        action: 'approved' | 'edited' | 'skipped'
        """
        if action == "skipped":
            # No style signals from a skip
            logger.info("Skill update skipped for %s (action=skip)", company_name)
            return

        content = self.read()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if action == "approved" and edited_body is None:
            note = (
                f"\n### Approved draft — {company_name} ({stage}) — {timestamp}\n"
                f"Style worked. Subject: {draft_subject}\n"
                f"Opening: {draft_body[:120].strip()}...\n"
            )
        elif action == "edited" and edited_body:
            delta_note = _summarize_delta(draft_body, edited_body)
            note = (
                f"\n### Edited draft — {company_name} ({stage}) — {timestamp}\n"
                f"Original opening: {draft_body[:120].strip()}...\n"
                f"Edit delta: {delta_note}\n"
            )
        else:
            return

        updated = content + note
        self.write(updated)
        logger.info("Skill file updated after %s for %s", action, company_name)


def _summarize_delta(original: str, edited: str) -> str:
    """
    Simple delta: note the first meaningful difference between original
    and edited bodies (first 300 chars of each, compared).
    """
    orig_words = original.split()
    edit_words = edited.split()
    if orig_words[:5] != edit_words[:5]:
        return f"Opening changed. Was: '{' '.join(orig_words[:8])}...' → '{' '.join(edit_words[:8])}...'"
    if len(edit_words) < len(orig_words) * 0.8:
        return "Significantly shortened"
    return f"Tone/content adjusted. Edited length: {len(edit_words)} words vs {len(orig_words)} original"
