"""Reflector for post-analysis learning.

After each analysis, the reflector extracts patterns and insights
that can be stored for future reference.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jirin.core.state import AnalysisState
from jirin.core.context import ExecutionContext
from jirin.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


REFLECT_PROMPT = """You are an Android stability analysis reviewer. Given the following analysis result, extract the key learnings:

1. What was the root cause pattern?
2. What were the key indicators that led to the diagnosis?
3. What is the recommended solution?
4. Is this a common pattern that might recur?
5. What category does this root cause belong to?

Provide your response as a JSON object:
{
    "root_cause_pattern": "Brief description of the pattern",
    "key_indicators": ["list of key indicators"],
    "solution_category": "Category of the solution",
    "is_common_pattern": true/false,
    "recurrence_likelihood": "high/medium/low",
    "tags": ["relevant tags for future retrieval"]
}

Analysis result:
{analysis}
"""


class Reflector:
    """Post-analysis reflection module.

    Reviews completed analyses and extracts reusable patterns
    for the knowledge base.
    """

    def __init__(self, context: ExecutionContext) -> None:
        self.context = context

    async def reflect(self, state: AnalysisState) -> dict[str, Any]:
        """Reflect on a completed analysis.

        Args:
            state: Completed analysis state.

        Returns:
            Extracted learnings as a dictionary.
        """
        if not state.agent_results:
            return {}

        # Build analysis summary for reflection
        analysis_text = self._build_analysis_summary(state)

        # Use LLM to extract patterns
        learnings = await self._extract_learnings(analysis_text)

        # Add metadata
        learnings["issue_type"] = state.primary_type.value
        learnings["log_source"] = state.log_source
        learnings["analysis_summary"] = self._summarize(state)

        return learnings

    def _build_analysis_summary(self, state: AnalysisState) -> str:
        """Build a text summary of the analysis for reflection."""
        parts = []
        for agent_name, result in state.agent_results.items():
            parts.append(f"Agent: {agent_name}")
            parts.append(f"Root Cause: {result.root_cause}")
            parts.append(f"Evidence: {', '.join(result.key_evidence)}")
            parts.append(f"Suggestions: {', '.join(result.suggestions)}")
            parts.append("")

        if state.final_report:
            parts.append(f"Final Report:\n{state.final_report[:2000]}")

        return "\n".join(parts)

    async def _extract_learnings(self, analysis_text: str) -> dict[str, Any]:
        """Use LLM to extract learnings from analysis.

        Args:
            analysis_text: Analysis summary text.

        Returns:
            Extracted learnings.
        """
        llm_config = self.context.get_llm_config()
        client = LLMClient(llm_config)

        response = await client.complete(
            messages=[
                {"role": "user", "content": REFLECT_PROMPT.format(analysis=analysis_text)},
            ],
            max_tokens=500,
        )

        if not response.success:
            logger.warning("Reflector LLM call failed: %s", response.error)
            return {"raw_analysis": analysis_text[:500]}

        return self._parse_learnings(response.content)

    def _parse_learnings(self, content: str) -> dict[str, Any]:
        """Parse LLM response into learnings dict."""
        try:
            # Match outermost braces to handle nested JSON
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end > start:
                return json.loads(content[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

        return {"raw_learnings": content[:500]}

    def _summarize(self, state: AnalysisState) -> str:
        """Create a brief summary of the analysis."""
        parts = []
        if state.detected_types:
            types = ", ".join(t.value.upper() for t in state.detected_types)
            parts.append(f"Issue: {types}")

        for result in state.agent_results.values():
            if result.root_cause:
                parts.append(f"Root Cause: {result.root_cause}")
            if result.responsible_party:
                parts.append(f"Responsible: {result.responsible_party}")

        return " | ".join(parts)
