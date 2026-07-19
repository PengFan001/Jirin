"""Generic Markdown exporter.

Exports Jirin knowledge as a portable Markdown documentation package.
"""

from __future__ import annotations

from pathlib import Path

from jirin.export.base import BaseExporter


INDEX_TEMPLATE = """# Jirin - Android Stability Analysis Knowledge Base

## Overview

This package contains knowledge and methodology for analyzing Android stability issues.

## Contents

- **je/**: Java Exception analysis (overview, common exceptions, lifecycle, Binder, system_server)
- **anr/**: ANR analysis (overview, input dispatching, service/broadcast, lock contention, Binder)
- **ne/**: Native Exception analysis (overview, signal details, tombstone, memory issues, debug tools)
- **memory/**: Memory leak analysis (overview, common patterns, OOM kill)
- **system/**: System stability (watchdog, LMK, system_server crash)
- **analysis_flow.md**: Step-by-step analysis methodology

## How to Use

1. Identify the issue type from the log (JE/ANR/NE)
2. Refer to the corresponding knowledge directory
3. Follow the analysis flow methodology
4. Use the responsibility matrix to determine ownership

## Agent Prompts

The `prompts/` directory contains system prompts for specialized analysis agents.
These can be used with any LLM to get expert-level analysis.
"""


class GenericExporter(BaseExporter):
    """Export as generic Markdown documentation package."""

    def export(self, output_dir: Path) -> None:
        """Export generic documentation.

        Args:
            output_dir: Target directory.
        """
        self._ensure_output_dir(output_dir)

        # Write index
        index_file = output_dir / "index.md"
        index_file.write_text(INDEX_TEMPLATE, encoding="utf-8")

        # Copy knowledge files (preserving directory structure)
        knowledge = self._read_static_knowledge()
        for rel_path, content in knowledge.items():
            # Skip duplicate entries (we store both "je/overview.md" and "overview.md")
            if "/" not in rel_path:
                continue  # Skip flat filename entries, prefer relative paths
            target = output_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        # Export prompts
        prompts_dir = output_dir / "prompts"
        self._ensure_output_dir(prompts_dir)

        prompts = self._get_agent_prompts()
        for agent_name, prompt in prompts.items():
            prompt_file = prompts_dir / f"{agent_name}_prompt.md"
            prompt_file.write_text(
                f"# {agent_name} System Prompt\n\n```\n{prompt}\n```\n",
                encoding="utf-8",
            )
