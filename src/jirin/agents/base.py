"""Base agent class for specialized analysis agents.

All specialized agents (JE, ANR, NE) inherit from this base class,
which provides common functionality for LLM interaction, knowledge retrieval,
and result construction.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from jirin.core.state import AnalysisState, AgentResult, IssueType
from jirin.core.context import ExecutionContext
from jirin.core.llm_client import LLMClient
from jirin.tools.search.code_search import CodeSearch

logger = logging.getLogger(__name__)

# Language instructions to append to system prompts
LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "zh-CN": "\n\nIMPORTANT: Please provide your ENTIRE response in Chinese (Simplified, 简体中文). "
             "All analysis, explanations, and suggestions must be in Chinese.",
    "en-US": "",  # Default, no extra instruction needed
    "ja-JP": "\n\nIMPORTANT: Please provide your ENTIRE response in Japanese (日本語). "
             "All analysis, explanations, and suggestions must be in Japanese.",
}


class BaseAgent(ABC):
    """Abstract base class for specialized analysis agents.

    Provides:
    - LLM interaction via httpx (OpenAI-compatible API)
    - Knowledge retrieval from knowledge base
    - Similar case retrieval for few-shot learning
    - Standard result construction
    """

    agent_name: str = "base"
    issue_type: IssueType = IssueType.UNKNOWN

    def __init__(self, context: ExecutionContext) -> None:
        self.context = context

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent.

        Each specialized agent must define its own domain-specific
        system prompt that guides the LLM's analysis behavior.
        """
        ...

    @abstractmethod
    def build_analysis_prompt(self, state: AnalysisState) -> str:
        """Build the user prompt for analysis.

        Args:
            state: Current analysis state with parsed data and knowledge.

        Returns:
            Formatted prompt string for the LLM.
        """
        ...

    async def analyze(self, state: AnalysisState) -> AgentResult:
        """Run the full analysis pipeline for this agent.

        Args:
            state: Shared analysis state.

        Returns:
            AgentResult with analysis findings.
        """
        # Build prompts
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_analysis_prompt(state)

        # Inject relevant knowledge
        knowledge_context = self._get_knowledge_context(state)
        if knowledge_context:
            user_prompt = f"{user_prompt}\n\n--- Relevant Knowledge ---\n{knowledge_context}"

        # Inject similar cases for few-shot
        similar_cases_context = self._get_similar_cases_context(state)
        if similar_cases_context:
            user_prompt = f"{user_prompt}\n\n--- Similar Historical Cases ---\n{similar_cases_context}"

        # Inject AOSP source code context
        source_context = self._get_source_context(state)
        if source_context:
            user_prompt = f"{user_prompt}\n\n--- Related AOSP Source Paths ---\n{source_context}"

        # Call LLM
        llm_response = await self._call_llm(system_prompt, user_prompt)

        # Parse response into structured result
        result = self._parse_response(llm_response, state)
        return result

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call LLM with retry, timeout, and error handling.

        Args:
            system_prompt: System instructions.
            user_prompt: User query with log data.

        Returns:
            LLM response text, or error message on failure.
        """
        llm_config = self.context.get_llm_config()
        client = LLMClient(llm_config)

        # Append language instruction if configured
        language = self.context.get_output_language()
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, "")
        if lang_instruction:
            system_prompt = system_prompt + lang_instruction

        response = await client.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        if not response.success:
            logger.error("LLM call failed for %s: %s", self.agent_name, response.error)
            return f"[LLM Error: {response.error}]"

        return response.content

    def _get_knowledge_context(self, state: AnalysisState) -> str:
        """Get relevant knowledge snippets from state."""
        if not state.relevant_knowledge:
            return ""
        return "\n\n".join(state.relevant_knowledge[:5])

    def _get_similar_cases_context(self, state: AnalysisState) -> str:
        """Format similar cases for few-shot context with feedback awareness.

        Cases with positive feedback are prioritized.
        Cases with corrections include the correction note so the LLM
        can avoid repeating the same mistake.
        """
        if not state.similar_cases:
            return ""

        # Sort: cases with positive feedback first, then corrections, then others
        def _feedback_priority(case: dict) -> int:
            feedbacks = case.get("feedback", [])
            for fb in feedbacks:
                if fb.get("type") == "positive":
                    return 0
            for fb in feedbacks:
                if fb.get("type") == "correction":
                    return 1
            return 2

        sorted_cases = sorted(state.similar_cases[:5], key=_feedback_priority)

        parts = []
        for i, case in enumerate(sorted_cases[:3], 1):
            root_cause = case.get("root_cause", "Unknown")
            analysis = case.get("analysis_summary", "N/A")
            solution = case.get("solution", "N/A")

            case_text = (
                f"Case {i}:\n"
                f"  Root Cause: {root_cause}\n"
                f"  Analysis: {analysis}\n"
                f"  Solution: {solution}"
            )

            # Append correction notes if present
            feedbacks = case.get("feedback", [])
            corrections = [fb for fb in feedbacks if fb.get("type") == "correction"]
            if corrections:
                latest = corrections[-1]
                case_text += (
                    f"\n  NOTE: A previous user corrected this analysis: "
                    f"{latest.get('content', '')}"
                )
                case_text += "\n  Please avoid making the same mistake."

            # Mark positively-reviewed cases
            positives = [fb for fb in feedbacks if fb.get("type") == "positive"]
            if positives:
                case_text += "\n  [Verified by user as accurate]"

            parts.append(case_text)
        return "\n\n".join(parts)

    def _get_source_context(self, state: AnalysisState) -> str:
        """Get AOSP source code context for the current issue type.

        Uses built-in framework path knowledge (always available)
        and optionally local AOSP source search if configured.

        Args:
            state: Current analysis state.

        Returns:
            Formatted source context string, or empty string.
        """
        try:
            source_cfg = self.context.get_source_config()
            source_dir = source_cfg.get("aosp_source_dir")
            searcher = CodeSearch(source_dir=source_dir)

            # Get parsed data for this issue type as context
            issue_key = self.issue_type.value
            parsed_context = state.parsed_data.get(issue_key, {})

            return searcher.format_source_context(issue_key, parsed_context)
        except Exception:
            return ""

    def _parse_response(self, response: str, state: AnalysisState) -> AgentResult:
        """Parse LLM response into structured AgentResult.

        Default implementation does basic extraction. Subclasses can override
        for more sophisticated parsing.
        """
        result = AgentResult(
            agent_name=self.agent_name,
            issue_type=self.issue_type,
            confidence=0.5,
        )

        # Try to extract JSON from response
        try:
            json_match = None
            # Look for code block with JSON
            json_block = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_block:
                json_match = json_block.group(1)
            else:
                # Try to find raw JSON object by matching outermost braces
                start = response.find("{")
                end = response.rfind("}")
                if start != -1 and end > start:
                    json_match = response[start:end + 1]

            if json_match:
                data = json.loads(json_match)
                result.root_cause = data.get("root_cause", "")
                result.responsible_party = data.get("responsible_party", "")
                result.analysis_detail = data.get("analysis_detail", "")
                result.key_evidence = data.get("key_evidence", [])
                result.suggestions = data.get("suggestions", [])
                result.confidence = float(data.get("confidence", 0.5))
                result.metadata = data.get("metadata", {})
        except (json.JSONDecodeError, ValueError):
            # If JSON parsing fails, use the raw response as analysis detail
            result.analysis_detail = response

        return result
