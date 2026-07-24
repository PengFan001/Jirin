"""Summary agent for synthesizing final analysis report.

Combines results from all specialized agents into a comprehensive
analysis report with root cause, responsibility, and action items.
"""

from __future__ import annotations

from jirin.core.state import AnalysisState
from jirin.core.context import ExecutionContext
from jirin.core.llm_client import LLMClient
from jirin.agents.base import LANGUAGE_INSTRUCTIONS


SUMMARY_SYSTEM_PROMPT = """You are an Android stability analysis report generator. Your job is to synthesize analysis results from specialized agents into a clear, actionable report.

Your report should:
1. Clearly state the root cause in one sentence
2. Identify the responsible party (app developer, SDK vendor, system/framework, or driver)
3. Explain the analysis process so the reader can understand the reasoning
4. Provide actionable fix suggestions with priority
5. Suggest how to track and close this issue (闭环路径)
6. Rate the confidence of the analysis

Format the report in clear Markdown with sections:
- Issue Summary (one-line description)
- Root Cause Analysis
- Responsibility Assignment
- Evidence Analysis
- Fix Suggestions (prioritized)
- Closure Path (how to track and resolve)
- Confidence Level

Be precise, technical, and actionable. Avoid vague statements.
"""


class SummaryAgent:
    """Agent that synthesizes results from all specialized agents.

    Takes the collected agent results and generates a comprehensive
    final report for the user.
    """

    def __init__(self, context: ExecutionContext) -> None:
        self.context = context

    async def summarize(self, state: AnalysisState) -> AnalysisState:
        """Generate the final analysis report.

        Args:
            state: Analysis state with all agent results.

        Returns:
            Updated state with final_report set.
        """
        if not state.agent_results:
            state.final_report = self._generate_empty_report(state)
            return state

        # Build synthesis prompt
        prompt = self._build_synthesis_prompt(state)

        # Call LLM via LLMClient (with retry, timeout, error handling)
        llm_config = self.context.get_llm_config()
        client = LLMClient(llm_config)

        # Append language instruction if configured
        system_prompt = SUMMARY_SYSTEM_PROMPT
        language = self.context.get_output_language()
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, "")
        if lang_instruction:
            system_prompt = system_prompt + lang_instruction

        response = await client.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )

        if response.success:
            state.final_report = response.content
        else:
            # Fallback: generate report without LLM
            state.final_report = self._generate_fallback_report(state)
            state.add_error(f"LLM synthesis failed: {response.error}")

        return state

    def _build_synthesis_prompt(self, state: AnalysisState) -> str:
        """Build prompt for LLM synthesis."""
        parts = [
            "Please synthesize the following analysis results into a comprehensive report.\n"
        ]

        parts.append(f"Issue Type(s): {', '.join(t.value.upper() for t in state.detected_types)}")
        parts.append(f"Log Source: {state.log_source or 'Unknown'}\n")

        for agent_name, result in state.agent_results.items():
            parts.append(f"\n--- {agent_name} Analysis ---")
            parts.append(f"Issue Type: {result.issue_type.value.upper()}")
            parts.append(f"Confidence: {result.confidence}")
            parts.append(f"Root Cause: {result.root_cause}")
            parts.append(f"Responsible Party: {result.responsible_party}")
            parts.append(f"Analysis Detail:\n{result.analysis_detail}")
            if result.key_evidence:
                parts.append(f"Key Evidence: {', '.join(result.key_evidence)}")
            if result.suggestions:
                parts.append(f"Suggestions: {', '.join(result.suggestions)}")

        if state.similar_cases:
            parts.append("\n--- Similar Historical Cases ---")
            for i, case in enumerate(state.similar_cases[:3], 1):
                parts.append(
                    f"Case {i}: {case.get('root_cause', 'N/A')} "
                    f"-> {case.get('solution', 'N/A')}"
                )

        # Inject cross-type correlation analysis (from correlator node, MIXED only)
        correlation = state.parsed_data.get("correlation")
        if correlation:
            parts.append("\n--- Cross-Type Correlation Analysis ---")
            parts.append(correlation)
            parts.append(
                "\nIMPORTANT: The correlation analysis above identifies causal "
                "relationships between different issue types. Incorporate the "
                "causal chain, primary root cause, and fix priority into your report."
            )

        return "\n".join(parts)

    def _generate_empty_report(self, state: AnalysisState) -> str:
        """Generate report when no agent results are available."""
        return (
            "# Analysis Report\n\n"
            "## Issue Summary\n"
            "Unable to classify the stability issue type from the provided log.\n\n"
            "## Recommendations\n"
            "- Ensure the log contains recognizable crash/ANR patterns\n"
            "- Check if the log is complete and not truncated\n"
            "- Try providing a more specific log excerpt\n"
        )

    def _generate_fallback_report(self, state: AnalysisState) -> str:
        """Generate report without LLM when LLM synthesis fails."""
        parts = ["# Analysis Report\n"]

        # Summary
        types_str = ", ".join(t.value.upper() for t in state.detected_types)
        parts.append(f"## Issue Summary\nDetected issue type(s): {types_str}\n")

        # Agent results
        for agent_name, result in state.agent_results.items():
            parts.append(f"\n## {result.issue_type.value.upper()} Analysis")
            parts.append(f"**Confidence**: {result.confidence:.0%}")
            if result.root_cause:
                parts.append(f"\n**Root Cause**: {result.root_cause}")
            if result.responsible_party:
                parts.append(f"\n**Responsible Party**: {result.responsible_party}")
            if result.analysis_detail:
                parts.append(f"\n**Analysis**:\n{result.analysis_detail}")
            if result.key_evidence:
                parts.append(f"\n**Key Evidence**:")
                for evidence in result.key_evidence:
                    parts.append(f"- {evidence}")
            if result.suggestions:
                parts.append(f"\n**Suggestions**:")
                for suggestion in result.suggestions:
                    parts.append(f"- {suggestion}")

        return "\n".join(parts)
