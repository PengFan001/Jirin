"""LangGraph agent graph definition.

Defines the multi-agent orchestration graph for stability issue analysis.
Uses a supervisor pattern where the Orchestrator routes tasks to specialized agents.
Supports true parallel fan-out via LangGraph Send API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.types import Send

from jirin.core.state import AnalysisState, IssueType
from jirin.core.context import ExecutionContext
from jirin.core.llm_client import LLMClient
from jirin.core.orchestrator import OrchestratorAgent
from jirin.agents.je_agent import JEAgent
from jirin.agents.anr_agent import ANRAgent
from jirin.agents.ne_agent import NEAgent
from jirin.agents.summary_agent import SummaryAgent

logger = logging.getLogger(__name__)


def _merge_agent_results(
    existing: dict[str, Any], new: dict[str, Any]
) -> dict[str, Any]:
    """Reducer: merge agent_results dicts from parallel branches."""
    return {**existing, **new}


class GraphState(TypedDict):
    """LangGraph state schema with reducers for parallel branch merging.

    The key reducer is on ``agent_results``: when multiple agent nodes
    run in parallel via Send, their individual results are merged into
    a single dict instead of being overwritten.
    """
    raw_log: str
    log_source: str
    detected_types: list[Any]
    primary_type: Any
    parsed_data: dict[str, Any]
    agent_results: Annotated[dict[str, Any], _merge_agent_results]
    relevant_knowledge: list[Any]
    similar_cases: list[Any]
    final_report: str
    execution_path: list[Any]
    errors: list[Any]
    metadata: dict[str, Any]

# Mapping from IssueType to agent node name
AGENT_NODE_MAP = {
    IssueType.JE: "je_agent",
    IssueType.ANR: "anr_agent",
    IssueType.NE: "ne_agent",
}


class AnalysisGraph:
    """Multi-agent analysis graph using LangGraph.

    Graph flow:
    1. orchestrator: Classifies issue type and decides routing
    2. route_to_agents: Dispatches to specialized agents (true parallel via Send)
    3. specialized agents: JE/ANR/NE analysis (run in parallel)
    4. correlator: (MIXED only) Cross-type causal correlation analysis
    5. summary: Synthesizes results into final report
    """

    def __init__(self, context: ExecutionContext) -> None:
        self.context = context
        self.orchestrator = OrchestratorAgent(context)
        self.je_agent = JEAgent(context)
        self.anr_agent = ANRAgent(context)
        self.ne_agent = NEAgent(context)
        self.summary_agent = SummaryAgent(context)
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph with Send-based fan-out."""
        graph = StateGraph(GraphState)

        # Add nodes
        graph.add_node("orchestrator", self._orchestrator_node)
        graph.add_node("je_agent", self._je_agent_node)
        graph.add_node("anr_agent", self._anr_agent_node)
        graph.add_node("ne_agent", self._ne_agent_node)
        graph.add_node("correlator", self._correlator_node)
        graph.add_node("summary", self._summary_node)

        # Entry point
        graph.set_entry_point("orchestrator")

        # After orchestrator, use Send API for true fan-out
        graph.add_conditional_edges(
            "orchestrator",
            self._fan_out_to_agents,
            {
                "je_agent": "je_agent",
                "anr_agent": "anr_agent",
                "ne_agent": "ne_agent",
                "summary": "summary",
            },
        )

        # All agents route to correlator (MIXED) or summary (single type)
        agent_edges_map = {
            "correlator": "correlator",
            "summary": "summary",
        }
        graph.add_conditional_edges(
            "je_agent", self._route_to_correlator_or_summary, agent_edges_map
        )
        graph.add_conditional_edges(
            "anr_agent", self._route_to_correlator_or_summary, agent_edges_map
        )
        graph.add_conditional_edges(
            "ne_agent", self._route_to_correlator_or_summary, agent_edges_map
        )

        # Correlator leads to summary
        graph.add_edge("correlator", "summary")

        # Summary leads to END
        graph.add_edge("summary", END)

        return graph.compile()

    def _orchestrator_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Orchestrator node: classify and decide routing."""
        logger.info("Orchestrator: classifying issue type")
        analysis_state = AnalysisState(**state)
        analysis_state = self.orchestrator.classify_and_route(analysis_state)
        logger.info(
            "Orchestrator: detected types=%s, primary=%s",
            [t.value for t in analysis_state.detected_types],
            analysis_state.primary_type.value,
        )
        return analysis_state.model_dump()

    def _fan_out_to_agents(self, state: dict[str, Any]) -> list[Send] | str:
        """Determine which agents to run and return Send objects for parallel execution.

        For single issue types, returns a single Send.
        For mixed issue types, returns multiple Sends for parallel execution.
        If no actionable types detected, routes directly to summary.
        """
        detected = state.get("detected_types", [])
        type_set = set(detected)

        if not type_set or type_set == {IssueType.UNKNOWN}:
            logger.info("No actionable issue types detected, routing to summary")
            return "summary"

        # Determine which agents to invoke
        agents_to_run = []
        for issue_type in type_set:
            if issue_type in AGENT_NODE_MAP:
                agents_to_run.append(issue_type)

        if not agents_to_run:
            return "summary"

        logger.info("Fan-out: dispatching to agents: %s", [t.value for t in agents_to_run])

        # Return Send objects for LangGraph to execute (potentially in parallel)
        return [
            Send(AGENT_NODE_MAP[issue_type], state)
            for issue_type in agents_to_run
        ]

    def _je_agent_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """JE analysis node (sync for thread pool execution)."""
        logger.info("JE Agent: starting analysis")
        analysis_state = AnalysisState(**state)
        result = asyncio.run(self.je_agent.analyze(analysis_state))
        analysis_state.add_result(result)
        logger.info("JE Agent: analysis complete, confidence=%.2f", result.confidence)
        return analysis_state.model_dump()

    def _anr_agent_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """ANR analysis node (sync for thread pool execution)."""
        logger.info("ANR Agent: starting analysis")
        analysis_state = AnalysisState(**state)
        result = asyncio.run(self.anr_agent.analyze(analysis_state))
        analysis_state.add_result(result)
        logger.info("ANR Agent: analysis complete, confidence=%.2f", result.confidence)
        return analysis_state.model_dump()

    def _ne_agent_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """NE analysis node (sync for thread pool execution)."""
        logger.info("NE Agent: starting analysis")
        analysis_state = AnalysisState(**state)
        result = asyncio.run(self.ne_agent.analyze(analysis_state))
        analysis_state.add_result(result)
        logger.info("NE Agent: analysis complete, confidence=%.2f", result.confidence)
        return analysis_state.model_dump()

    def _route_to_correlator_or_summary(self, state: dict[str, Any]) -> str:
        """Route to correlator if MIXED type, otherwise to summary."""
        primary = state.get("primary_type")
        if primary == IssueType.MIXED:
            logger.info("MIXED type detected, routing to correlator")
            return "correlator"
        return "summary"

    def _correlator_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Correlator node: analyze causal relationships between multiple issue types.

        Only activated when primary_type == MIXED and multiple agent results exist.
        Uses LLM to determine if one issue type caused another.
        """
        logger.info("Correlator: analyzing cross-type relationships")
        analysis_state = AnalysisState(**state)

        if len(analysis_state.agent_results) < 2:
            logger.info("Correlator: fewer than 2 agent results, skipping correlation")
            return analysis_state.model_dump()

        # Build correlation prompt
        prompt = self._build_correlation_prompt(analysis_state)

        llm_config = self.context.get_llm_config()
        if not llm_config.get("api_key") and llm_config.get("provider") != "ollama":
            logger.warning("Correlator: no LLM configured, skipping correlation")
            return analysis_state.model_dump()

        client = LLMClient(llm_config, max_retries=2, timeout=30.0)
        response = asyncio.run(
            client.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000,
            )
        )

        if response.success:
            analysis_state.parsed_data["correlation"] = response.content
            logger.info("Correlator: cross-type correlation analysis complete")
        else:
            logger.warning("Correlator: LLM call failed: %s", response.error)
            analysis_state.add_error(f"Correlation analysis failed: {response.error}")

        return analysis_state.model_dump()

    def _build_correlation_prompt(self, state: AnalysisState) -> str:
        """Build prompt for cross-type causal correlation analysis."""
        parts = [
            "You are analyzing an Android stability issue that involves MULTIPLE issue types.\n"
            "Your task is to determine the causal relationships between them.\n"
        ]

        parts.append(f"Issue Types Detected: {', '.join(t.value.upper() for t in state.detected_types)}\n")

        for agent_name, result in state.agent_results.items():
            parts.append(f"\n--- {result.issue_type.value.upper()} Analysis ---")
            parts.append(f"Root Cause: {result.root_cause}")
            parts.append(f"Responsible Party: {result.responsible_party}")
            if result.key_evidence:
                parts.append(f"Key Evidence: {', '.join(result.key_evidence[:5])}")
            if result.analysis_detail:
                parts.append(f"Analysis Detail:\n{result.analysis_detail[:1500]}")

        parts.append("""
Analyze the causal relationships and respond as JSON:
{
    "causal_chain": "Description of how the issues are related (e.g., 'JE in app code caused main thread blockage, triggering ANR')",
    "primary_root_cause": "The fundamental root cause that triggered the chain",
    "fix_priority": ["issue_type_to_fix_first", "second", "third"],
    "cross_type_evidence": ["evidence_1_linkin_different_types", "evidence_2"],
    "correlation_confidence": 0.0-1.0
}""")

        return "\n".join(parts)

    def _summary_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Summary node: synthesize final report (sync for thread pool execution)."""
        logger.info("Summary Agent: synthesizing final report")
        analysis_state = AnalysisState(**state)
        final_state = asyncio.run(self.summary_agent.summarize(analysis_state))
        logger.info("Summary Agent: report generated")
        return final_state.model_dump()

    async def analyze(self, raw_log: str, log_source: str = "") -> AnalysisState:
        """Run the full analysis pipeline.

        Args:
            raw_log: Raw log content to analyze.
            log_source: Optional source identifier.

        Returns:
            Final AnalysisState with report and results.
        """
        initial_state = AnalysisState(raw_log=raw_log, log_source=log_source)
        result = await self._graph.ainvoke(initial_state.model_dump())
        return AnalysisState(**result)
