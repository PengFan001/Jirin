"""Analyze command implementation.

Core analysis workflow: load config -> build graph -> run analysis -> learn.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jirin.core.state import AnalysisState
from jirin.core.context import ExecutionContext
from jirin.core.agent_graph import AnalysisGraph

logger = logging.getLogger(__name__)


async def analyze_cmd(
    log_content: str,
    log_source: str = "",
    config_path: Path | None = None,
    verbose: bool = False,
) -> AnalysisState:
    """Run the analysis pipeline with post-analysis learning.

    Args:
        log_content: Raw log content to analyze.
        log_source: Source identifier for the log.
        config_path: Path to configuration file.
        verbose: Whether to show verbose output.

    Returns:
        AnalysisState with final report.
    """
    # Load configuration
    context = ExecutionContext(config_path=config_path)

    if verbose:
        llm_config = context.get_llm_config()
        logger.info("[Config] LLM: %s/%s", llm_config.get("provider"), llm_config.get("model"))

    # Build analysis graph
    graph = AnalysisGraph(context)

    # Run analysis
    result = await graph.analyze(raw_log=log_content, log_source=log_source)

    # Post-analysis learning (if analysis was successful)
    if result.agent_results:
        case_id = await _run_learning_pipeline(context, result)
        if case_id:
            # Store case_id in metadata for feedback association
            result.metadata["case_id"] = case_id

    return result


async def _run_learning_pipeline(
    context: ExecutionContext,
    state: AnalysisState,
) -> str | None:
    """Run the post-analysis learning pipeline.

    Steps:
    1. Reflector: extract root cause patterns
    2. Classifier: categorize the root cause
    3. CaseStore: persist the case
    4. KnowledgeManager: build embedding for future retrieval
    5. Memory: save long-term insights

    Args:
        context: Execution context with shared resources.
        state: Completed analysis state.

    Returns:
        case_id if a case was saved, None otherwise.
    """
    try:
        from jirin.learning.reflector import Reflector
        from jirin.learning.classifier import Classifier
        from jirin.learning.memory import MemoryManager

        # Step 1: Reflect on the analysis
        reflector = Reflector(context)
        learnings = await reflector.reflect(state)

        if not learnings:
            logger.debug("No learnings extracted, skipping learning pipeline")
            return None

        # Step 2: Classify the root cause
        classifier = Classifier()
        root_cause_category = classifier.classify(learnings)
        learnings["root_cause_category"] = root_cause_category

        # Step 3: Save to case store
        case_store = context.case_store
        case_data = {
            "issue_type": state.primary_type.value,
            "log_excerpt": state.raw_log[:2000],
            "analysis_result": {
                "agent_results": {
                    name: r.model_dump() for name, r in state.agent_results.items()
                },
                "learnings": learnings,
            },
            "metadata": {
                "log_source": state.log_source,
                "detected_types": [t.value for t in state.detected_types],
            },
            "root_cause": learnings.get("root_cause_pattern", ""),
            "root_cause_category": root_cause_category,
        }
        case_id = case_store.save_case(case_data)
        logger.info("Case saved: %s (category: %s)", case_id, root_cause_category)

        # Step 4: Build embedding for future retrieval
        knowledge_manager = context.knowledge_manager
        knowledge_manager.store_case_embedding(case_id, {
            "issue_type": state.primary_type.value,
            "root_cause": learnings.get("root_cause_pattern", ""),
            "analysis_summary": learnings.get("analysis_summary", ""),
            "log_excerpt": state.raw_log[:500],
        })

        # Step 5: Save long-term memory insights
        storage_cfg = context.get_storage_config()
        memory = MemoryManager(memory_dir=storage_cfg.get("memory_dir", "data/memory"))
        if learnings.get("is_common_pattern"):
            insight_text = (
                f"Pattern: {learnings.get('root_cause_pattern', '')} | "
                f"Indicators: {', '.join(learnings.get('key_indicators', []))} | "
                f"Solution: {learnings.get('solution_category', '')}"
            )
            memory.add_insight(
                insight=insight_text,
                category=root_cause_category,
                tags=learnings.get("tags", []),
            )

        logger.info("Learning pipeline complete for case %s", case_id)
        return case_id

    except Exception as e:
        # Learning failure should not block the analysis result
        logger.warning("Learning pipeline failed (non-fatal): %s", e)
        return None
