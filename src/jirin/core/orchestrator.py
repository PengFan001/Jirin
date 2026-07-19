"""Orchestrator agent for issue classification and routing.

The Orchestrator analyzes raw logs to determine issue types and decides
which specialized agents should handle the analysis.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from jirin.core.state import AnalysisState, IssueType
from jirin.core.context import ExecutionContext
from jirin.core.llm_client import LLMClient
from jirin.tools.log_parser.je_parser import parse_je_log
from jirin.tools.log_parser.anr_parser import parse_anr_log
from jirin.tools.log_parser.ne_parser import parse_ne_log

logger = logging.getLogger(__name__)


# Patterns for quick classification without LLM
JE_PATTERNS = [
    re.compile(r"java\.lang\.\w+Exception"),
    re.compile(r"java\.lang\.\w+Error"),
    re.compile(r"FATAL EXCEPTION"),
    re.compile(r"android\.util\.AndroidRuntimeException"),
    re.compile(r"Caused by: \w+"),
    re.compile(r"at [a-z]+\.[a-z]+\.\w+\.\w+\("),
    re.compile(r"Process: .*, PID: \d+"),
]

ANR_PATTERNS = [
    re.compile(r"ANR in"),
    re.compile(r"Subject: ANR"),
    re.compile(r"am_anr"),
    re.compile(r"Input dispatching timed out"),
    re.compile(r"executing service.*ANR"),
    re.compile(r"msgctxt 'ANR'"),
    re.compile(r"LOAD: [\d.]+"),
    re.compile(r"traces\.txt"),
]

NE_PATTERNS = [
    re.compile(r"signal \d+ \(SIG\w+\)"),
    re.compile(r"Abort message:"),
    re.compile(r"backtrace:"),
    re.compile(r"#[0-9]+ pc 0x[0-9a-fA-F]+"),
    re.compile(r"tombstone"),
    re.compile(r"Native crash"),
    re.compile(r"fatal signal \d+"),
    re.compile(r"DEBUG.*pid.*tid"),
]


class OrchestratorAgent:
    """Main orchestrator that classifies issues and routes to agents.

    Uses a two-phase approach:
    1. Rule-based pre-classification using regex patterns (fast, free)
    2. LLM-based classification for ambiguous cases (accurate)
    """

    def __init__(self, context: ExecutionContext) -> None:
        self.context = context

    def classify_and_route(self, state: AnalysisState) -> AnalysisState:
        """Classify the issue type and prepare routing information.

        Args:
            state: Current analysis state with raw log.

        Returns:
            Updated state with detected_types and primary_type set.
        """
        log = state.raw_log

        # Phase 1: Rule-based pre-classification
        detected = self._pattern_classify(log)

        # Phase 2: LLM classification for ambiguous or empty results
        if not detected or len(detected) > 1:
            llm_detected = self._llm_classify(log)
            if llm_detected:
                detected = llm_detected

        if not detected:
            detected = [IssueType.UNKNOWN]

        state.detected_types = detected

        # Determine primary type
        if len(detected) == 1:
            state.primary_type = detected[0]
        elif len(detected) > 1:
            state.primary_type = IssueType.MIXED
        else:
            state.primary_type = IssueType.UNKNOWN

        # Pre-parse log data for detected types
        state.parsed_data = self._extract_key_info(log, detected)

        # Retrieve relevant knowledge
        state.relevant_knowledge = self._retrieve_knowledge(detected)
        state.similar_cases = self._retrieve_similar_cases(log, detected)

        return state

    def _pattern_classify(self, log: str) -> list[IssueType]:
        """Quick rule-based classification using regex patterns."""
        detected: list[IssueType] = []

        je_score = sum(1 for p in JE_PATTERNS if p.search(log))
        anr_score = sum(1 for p in ANR_PATTERNS if p.search(log))
        ne_score = sum(1 for p in NE_PATTERNS if p.search(log))

        # Threshold: at least 2 pattern matches to classify
        if je_score >= 2:
            detected.append(IssueType.JE)
        if anr_score >= 2:
            detected.append(IssueType.ANR)
        if ne_score >= 2:
            detected.append(IssueType.NE)

        return detected

    def _llm_classify(self, log: str) -> list[IssueType]:
        """Use LLM to classify ambiguous logs."""
        llm_config = self.context.get_llm_config()
        if not llm_config.get("api_key") and llm_config.get("provider") != "ollama":
            return []

        # Truncate log for classification (first 4000 chars should be enough)
        log_excerpt = log[:4000] if len(log) > 4000 else log

        prompt = f"""You are an Android stability issue classifier. Analyze the following log excerpt and determine what type of stability issue(s) it contains.

Issue types:
- JE: Java Exception (FATAL EXCEPTION, uncaught exceptions, crash in Java code)
- ANR: Application Not Responding (input timeout, service timeout, system watchdog)
- NE: Native Exception (signal crash, tombstone, native memory issues)

Respond with ONLY a JSON array of issue types found, e.g. ["JE"], ["ANR"], ["JE", "ANR"], or [] if unclear.

Log excerpt:
```
{log_excerpt}
```

JSON response:"""

        client = LLMClient(llm_config, max_retries=1, timeout=15.0)
        response = client.complete_sync(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=100,
        )

        if not response.success:
            logger.warning("LLM classification failed: %s", response.error)
            return []

        return self._parse_llm_classification(response.content.strip())

    def _parse_llm_classification(self, content: str) -> list[IssueType]:
        """Parse LLM classification response."""
        try:
            # Try to extract JSON array from response
            match = re.search(r"\[.*?\]", content)
            if match:
                types = json.loads(match.group())
                result = []
                type_map = {
                    "je": IssueType.JE,
                    "anr": IssueType.ANR,
                    "ne": IssueType.NE,
                }
                for t in types:
                    t_lower = t.lower().strip()
                    if t_lower in type_map:
                        result.append(type_map[t_lower])
                return result
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    def _extract_key_info(
        self, log: str, detected: list[IssueType]
    ) -> dict[str, Any]:
        """Extract key information from log using specialized parsers.

        Delegates to the professional log parsers in tools/log_parser/
        which provide richer structured data than basic regex extraction.
        """
        parsed: dict[str, Any] = {}

        if IssueType.JE in detected:
            parsed["je"] = parse_je_log(log)
        if IssueType.ANR in detected:
            parsed["anr"] = parse_anr_log(log)
        if IssueType.NE in detected:
            parsed["ne"] = parse_ne_log(log)

        return parsed

    def _retrieve_knowledge(self, detected: list[IssueType]) -> list[str]:
        """Retrieve relevant knowledge for detected issue types."""
        try:
            km = self.context.knowledge_manager
            snippets = []
            for issue_type in detected:
                if issue_type in (IssueType.JE, IssueType.ANR, IssueType.NE):
                    results = km.search_static_knowledge(
                        query=f"{issue_type.value} analysis principles",
                        top_k=3,
                    )
                    snippets.extend(results)
            return snippets
        except Exception:
            return []

    def _retrieve_similar_cases(
        self, log: str, detected: list[IssueType]
    ) -> list[dict[str, Any]]:
        """Retrieve similar historical cases."""
        try:
            km = self.context.knowledge_manager
            cases = []
            for issue_type in detected:
                if issue_type in (IssueType.JE, IssueType.ANR, IssueType.NE):
                    results = km.search_similar_cases(
                        query=log[:2000],
                        issue_type=issue_type.value,
                        top_k=3,
                    )
                    cases.extend(results)
            return cases
        except Exception:
            return []
