"""Codex Agent exporter.

Exports Jirin knowledge as an AGENTS.md file compatible with
OpenAI Codex and similar AI coding assistants.
"""

from __future__ import annotations

from pathlib import Path

from jirin.export.base import BaseExporter


AGENTS_MD_TEMPLATE = """# Jirin - Android Stability Analyzer

This file provides guidance to Codex when working with Android stability issues in this repository.

## Overview

Jirin is an AI agent specialized in analyzing Android stability issues:
- **JE** (Java Exception): FATAL EXCEPTION, uncaught exceptions, crash in Java code
- **ANR** (Application Not Responding): Input timeout, service timeout, broadcast timeout
- **NE** (Native Exception): Signal crashes (SIGSEGV/SIGABRT/etc), tombstone analysis

## How to Analyze Stability Issues

### Step 1: Classify the Issue Type

Look for these patterns in the log:
- **JE**: `FATAL EXCEPTION`, `java.lang.*Exception`, Java stack traces with `at ...(...)`
- **ANR**: `ANR in`, `Input dispatching timed out`, `am_anr`, traces.txt content
- **NE**: `signal N (SIGxxx)`, `tombstone`, `#N pc 0x...` backtrace frames

### Step 2: Analyze Based on Type

#### Java Exception (JE) Analysis

{je_knowledge}

#### ANR Analysis

{anr_knowledge}

#### Native Exception (NE) Analysis

{ne_knowledge}

### Step 3: Output Format

Always provide analysis in this structure:

1. **Issue Type**: JE / ANR / NE
2. **Root Cause**: One clear sentence identifying the root cause
3. **Responsible Party**: app / SDK / system / driver
4. **Key Evidence**: Bullet points from the log supporting the conclusion
5. **Fix Suggestions**: Prioritized, actionable suggestions
6. **Closure Path**: How to track and resolve the issue
7. **Confidence**: High / Medium / Low

## Analysis Flow

{analysis_flow}

## Agent System Prompts

### JE Agent
{je_prompt}

### ANR Agent
{anr_prompt}

### NE Agent
{ne_prompt}
"""


class CodexExporter(BaseExporter):
    """Export as Codex-compatible AGENTS.md file.

    Creates an AGENTS.md file with embedded knowledge and prompts
    that Codex can use for Android stability analysis.
    """

    def export(self, output_dir: Path) -> None:
        """Export the AGENTS.md file.

        Args:
            output_dir: Target directory for the AGENTS.md file.
        """
        self._ensure_output_dir(output_dir)

        # Read knowledge
        knowledge = self._read_static_knowledge()

        # Read agent prompts
        prompts = self._get_agent_prompts()

        # Build AGENTS.md using directory structure
        je_knowledge = knowledge.get("je/je_overview.md", "")
        anr_knowledge = knowledge.get("anr/anr_overview.md", "")
        ne_knowledge = knowledge.get("ne/ne_overview.md", "")
        analysis_flow = knowledge.get("analysis_flow.md", "")

        agents_content = AGENTS_MD_TEMPLATE.format(
            je_knowledge=je_knowledge or "See jirin_knowledge/je/ for detailed JE knowledge.",
            anr_knowledge=anr_knowledge or "See jirin_knowledge/anr/ for detailed ANR knowledge.",
            ne_knowledge=ne_knowledge or "See jirin_knowledge/ne/ for detailed NE knowledge.",
            analysis_flow=analysis_flow or "See jirin_knowledge/analysis_flow.md",
            je_prompt=prompts.get("je_agent", ""),
            anr_prompt=prompts.get("anr_agent", ""),
            ne_prompt=prompts.get("ne_agent", ""),
        )

        # Write AGENTS.md
        agents_file = output_dir / "AGENTS.md"
        agents_file.write_text(agents_content, encoding="utf-8")

        # Also create a knowledge reference directory
        knowledge_dir = output_dir / "jirin_knowledge"
        self._ensure_output_dir(knowledge_dir)

        for rel_path, content in knowledge.items():
            if "/" not in rel_path:
                continue
            target = knowledge_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
