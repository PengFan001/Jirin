"""Cursor Rules exporter.

Exports Jirin knowledge as Cursor IDE rules files.
"""

from __future__ import annotations

from pathlib import Path

from jirin.export.base import BaseExporter


CURSOR_RULE_TEMPLATE = """# Jirin - Android Stability Analysis Rules

You are an expert Android stability analyst. When analyzing crash logs, ANR traces, or tombstones, follow these rules:

## Classification Rules

1. If the log contains "FATAL EXCEPTION" or Java stack traces -> Java Exception (JE)
2. If the log contains "ANR in" or "Input dispatching timed out" -> ANR
3. If the log contains "signal N (SIGxxx)" or tombstone data -> Native Exception (NE)

## JE Analysis Rules

{je_rules}

## ANR Analysis Rules

{anr_rules}

## NE Analysis Rules

{ne_rules}

## Report Format

Always structure your analysis as:

1. **Issue Type**: JE / ANR / NE
2. **Root Cause**: One clear sentence
3. **Responsible Party**: app / SDK / system / driver
4. **Evidence**: Bullet points of key findings
5. **Fix Suggestions**: Prioritized list
6. **Confidence**: High / Medium / Low
"""


class CursorRulesExporter(BaseExporter):
    """Export as Cursor IDE rules."""

    def export(self, output_dir: Path) -> None:
        """Export Cursor rules.

        Args:
            output_dir: Target directory.
        """
        self._ensure_output_dir(output_dir)

        knowledge = self._read_static_knowledge()

        # Build rules content using directory structure
        je_rules = knowledge.get("je/je_overview.md", "")[:3000]
        anr_rules = knowledge.get("anr/anr_overview.md", "")[:3000]
        ne_rules = knowledge.get("ne/ne_overview.md", "")[:3000]

        rules_content = CURSOR_RULE_TEMPLATE.format(
            je_rules=je_rules,
            anr_rules=anr_rules,
            ne_rules=ne_rules,
        )

        # Write main rules file
        rules_file = output_dir / "jirin.md"
        rules_file.write_text(rules_content, encoding="utf-8")

        # Write separate knowledge files
        knowledge_dir = output_dir / "knowledge"
        self._ensure_output_dir(knowledge_dir)

        for rel_path, content in knowledge.items():
            if "/" not in rel_path:
                continue
            target = knowledge_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
