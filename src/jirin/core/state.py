"""Shared state definition for multi-agent orchestration.

Defines the LangGraph state that flows between agents during analysis.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IssueType(str, Enum):
    """Type of stability issue."""

    JE = "je"  # Java Exception
    ANR = "anr"  # Application Not Responding
    NE = "ne"  # Native Exception
    MIXED = "mixed"  # Multiple issue types detected
    UNKNOWN = "unknown"


class AgentResult(BaseModel):
    """Result from a specialized analysis agent."""

    agent_name: str
    issue_type: IssueType
    confidence: float = Field(ge=0.0, le=1.0, description="Analysis confidence score")
    root_cause: str = Field(default="", description="Identified root cause")
    responsible_party: str = Field(default="", description="Responsible party identification")
    analysis_detail: str = Field(default="", description="Detailed analysis process")
    key_evidence: list[str] = Field(default_factory=list, description="Key evidence found")
    suggestions: list[str] = Field(default_factory=list, description="Fix suggestions")
    related_cases: list[str] = Field(default_factory=list, description="Related historical cases")
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisState(BaseModel):
    """LangGraph shared state for the analysis pipeline.

    This state flows through the agent graph and accumulates results
    from each specialized agent.
    """

    # Input
    raw_log: str = Field(default="", description="Raw log content to analyze")
    log_source: str = Field(default="", description="Source identifier for the log")

    # Classification
    detected_types: list[IssueType] = Field(
        default_factory=list, description="Detected issue types"
    )
    primary_type: IssueType = Field(
        default=IssueType.UNKNOWN, description="Primary issue type"
    )

    # Parsed log data
    parsed_data: dict[str, Any] = Field(
        default_factory=dict, description="Parsed log structures by type"
    )

    # Agent results
    agent_results: dict[str, AgentResult] = Field(
        default_factory=dict, description="Results keyed by agent name"
    )

    # Knowledge retrieval
    relevant_knowledge: list[str] = Field(
        default_factory=list, description="Retrieved knowledge snippets"
    )
    similar_cases: list[dict[str, Any]] = Field(
        default_factory=list, description="Similar historical cases"
    )

    # Final output
    final_report: str = Field(default="", description="Synthesized final report")

    # Execution metadata
    execution_path: list[str] = Field(
        default_factory=list, description="Record of executed agents"
    )
    errors: list[str] = Field(default_factory=list, description="Errors encountered")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (e.g. case_id for feedback)"
    )

    def add_result(self, result: AgentResult) -> None:
        """Add an agent result and record execution."""
        self.agent_results[result.agent_name] = result
        self.execution_path.append(result.agent_name)

    def add_error(self, error: str) -> None:
        """Record an error."""
        self.errors.append(error)
