"""Tests for Orchestrator classification logic (no LLM required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jirin.core.state import AnalysisState, IssueType
from jirin.core.orchestrator import OrchestratorAgent, JE_PATTERNS, ANR_PATTERNS, NE_PATTERNS
from jirin.core.context import ExecutionContext


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def orchestrator() -> OrchestratorAgent:
    """Create orchestrator with empty config (no LLM)."""
    context = ExecutionContext()
    return OrchestratorAgent(context)


class TestPatternClassification:
    """Test rule-based pre-classification (no LLM needed)."""

    def test_classifies_je(self, orchestrator: OrchestratorAgent) -> None:
        log = (FIXTURES_DIR / "sample_je.log").read_text(encoding="utf-8")
        result = orchestrator._pattern_classify(log)
        assert IssueType.JE in result

    def test_classifies_anr(self, orchestrator: OrchestratorAgent) -> None:
        log = (FIXTURES_DIR / "sample_anr.log").read_text(encoding="utf-8")
        result = orchestrator._pattern_classify(log)
        assert IssueType.ANR in result

    def test_classifies_ne(self, orchestrator: OrchestratorAgent) -> None:
        log = (FIXTURES_DIR / "sample_ne.log").read_text(encoding="utf-8")
        result = orchestrator._pattern_classify(log)
        assert IssueType.NE in result

    def test_rejects_empty(self, orchestrator: OrchestratorAgent) -> None:
        result = orchestrator._pattern_classify("")
        assert result == []

    def test_rejects_unrelated(self, orchestrator: OrchestratorAgent) -> None:
        log = "ActivityManager: Start proc 1234:com.example.app"
        result = orchestrator._pattern_classify(log)
        assert result == []

    def test_detects_mixed(self, orchestrator: OrchestratorAgent) -> None:
        # Combine JE and ANR content
        je_log = (FIXTURES_DIR / "sample_je.log").read_text(encoding="utf-8")
        anr_log = (FIXTURES_DIR / "sample_anr.log").read_text(encoding="utf-8")
        mixed = je_log + "\n" + anr_log
        result = orchestrator._pattern_classify(mixed)
        assert IssueType.JE in result
        assert IssueType.ANR in result


class TestClassifyAndRoute:
    """Test the full classify_and_route method."""

    def test_je_routing(self, orchestrator: OrchestratorAgent) -> None:
        log = (FIXTURES_DIR / "sample_je.log").read_text(encoding="utf-8")
        state = AnalysisState(raw_log=log)
        result = orchestrator.classify_and_route(state)
        assert result.primary_type == IssueType.JE
        assert IssueType.JE in result.detected_types

    def test_anr_routing(self, orchestrator: OrchestratorAgent) -> None:
        log = (FIXTURES_DIR / "sample_anr.log").read_text(encoding="utf-8")
        state = AnalysisState(raw_log=log)
        result = orchestrator.classify_and_route(state)
        assert result.primary_type == IssueType.ANR

    def test_ne_routing(self, orchestrator: OrchestratorAgent) -> None:
        log = (FIXTURES_DIR / "sample_ne.log").read_text(encoding="utf-8")
        state = AnalysisState(raw_log=log)
        result = orchestrator.classify_and_route(state)
        assert result.primary_type == IssueType.NE

    def test_unknown_for_empty(self, orchestrator: OrchestratorAgent) -> None:
        state = AnalysisState(raw_log="random text without patterns")
        result = orchestrator.classify_and_route(state)
        assert result.primary_type == IssueType.UNKNOWN
