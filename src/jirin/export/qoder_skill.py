"""Qoder Skill exporter.

Exports the Jirin agent as a Qoder-compatible skill that can be
installed and used in Qoder IDE.
"""

from __future__ import annotations

from pathlib import Path

from jirin.export.base import BaseExporter


SKILL_MD_TEMPLATE = """# Jirin - Android Stability Analyzer

An AI agent specialized in analyzing Android stability issues (JE, ANR, NE).

## Description

Jirin helps Android developers analyze stability issues by:
- Classifying issue types (Java Exception, ANR, Native Exception)
- Identifying root causes from log analysis
- Determining responsibility (app/SDK/system)
- Providing actionable fix suggestions
- Learning from past analyses

## Usage

When the user provides an Android crash log, ANR trace, or tombstone:

1. First classify the issue type by looking for these patterns:
   - **JE**: FATAL EXCEPTION, java.lang.*Exception, stack traces
   - **ANR**: "ANR in", traces.txt, Input dispatching timed out
   - **NE**: signal N (SIGxxx), tombstone, native backtrace

2. Analyze the issue following the methodology below.

3. Provide a structured report with:
   - Root cause
   - Responsible party
   - Evidence
   - Fix suggestions
   - Closure path

## Issue Analysis Methodology

### Java Exception (JE) Analysis

{je_knowledge}

### ANR Analysis

{anr_knowledge}

### Native Exception (NE) Analysis

{ne_knowledge}

### Analysis Flow

{analysis_flow}

## Agent Roles

### JE Agent
{je_prompt}

### ANR Agent
{anr_prompt}

### NE Agent
{ne_prompt}

## Output Format

Always provide analysis results in this structure:

1. **Issue Summary**: One-line description
2. **Root Cause**: Clear root cause identification
3. **Responsible Party**: app / SDK / system / driver
4. **Evidence**: Key evidence from the log
5. **Fix Suggestions**: Prioritized, actionable suggestions
6. **Closure Path**: How to track and resolve
7. **Confidence**: Analysis confidence level
"""


class QoderSkillExporter(BaseExporter):
    """Export Jirin as a Qoder Skill.

    Creates a SKILL.md file with embedded knowledge and prompts
    that can be used directly in Qoder.
    """

    def export(self, output_dir: Path) -> None:
        """Export the skill.

        Args:
            output_dir: Target directory for the skill.
        """
        self._ensure_output_dir(output_dir)

        # Read knowledge
        knowledge = self._read_static_knowledge()

        # Read agent prompts
        prompts = self._get_agent_prompts()

        # Build SKILL.md using directory structure
        je_knowledge = knowledge.get("je/je_overview.md", "")
        anr_knowledge = knowledge.get("anr/anr_overview.md", "")
        ne_knowledge = knowledge.get("ne/ne_overview.md", "")
        analysis_flow = knowledge.get("analysis_flow.md", "")

        skill_content = SKILL_MD_TEMPLATE.format(
            je_knowledge=je_knowledge or "Refer to assets/je/ for detailed JE knowledge.",
            anr_knowledge=anr_knowledge or "Refer to assets/anr/ for detailed ANR knowledge.",
            ne_knowledge=ne_knowledge or "Refer to assets/ne/ for detailed NE knowledge.",
            analysis_flow=analysis_flow or "Refer to assets/analysis_flow.md",
            je_prompt=prompts.get("je_agent", ""),
            anr_prompt=prompts.get("anr_agent", ""),
            ne_prompt=prompts.get("ne_agent", ""),
        )

        # Write SKILL.md
        skill_file = output_dir / "SKILL.md"
        skill_file.write_text(skill_content, encoding="utf-8")

        # Create assets directory with knowledge files
        assets_dir = output_dir / "assets"
        self._ensure_output_dir(assets_dir)

        for rel_path, content in knowledge.items():
            if "/" not in rel_path:
                continue
            target = assets_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
