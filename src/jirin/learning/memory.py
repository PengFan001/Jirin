"""Long-term memory management for the agent.

Manages persistent memory that persists across sessions, including
corrections, reinforced patterns, and learned insights.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class MemoryManager:
    """Long-term memory manager for the agent.

    Stores and retrieves persistent memories including:
    - Corrections: When the agent was wrong and was corrected
    - Reinforced patterns: When the agent was right and confirmed
    - Insights: General learnings from analysis experience
    """

    def __init__(self, memory_dir: str = "data/memory") -> None:
        self._memory_dir = Path(memory_dir)
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        self._corrections_file = self._memory_dir / "corrections.json"
        self._insights_file = self._memory_dir / "insights.json"

    def add_correction(
        self,
        original_analysis: str,
        correction: str,
        context: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Record a correction (when agent was wrong).

        Args:
            original_analysis: What the agent originally said.
            correction: The correct answer/explanation.
            context: Additional context about the correction.
            tags: Tags for retrieval.

        Returns:
            Memory ID.
        """
        corrections = self._load_corrections()
        memory_id = f"corr_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        corrections.append({
            "id": memory_id,
            "original": original_analysis,
            "correction": correction,
            "context": context,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
        })

        self._save_corrections(corrections)
        return memory_id

    def add_insight(
        self,
        insight: str,
        category: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Record a general insight or learning.

        Args:
            insight: The insight text.
            category: Category of the insight.
            tags: Tags for retrieval.

        Returns:
            Memory ID.
        """
        insights = self._load_insights()
        memory_id = f"ins_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        insights.append({
            "id": memory_id,
            "insight": insight,
            "category": category,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
        })

        self._save_insights(insights)
        return memory_id

    def get_corrections(
        self,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get stored corrections, optionally filtered by tags.

        Args:
            tags: Filter by tags.
            limit: Maximum results.

        Returns:
            List of correction records.
        """
        corrections = self._load_corrections()

        if tags:
            corrections = [
                c for c in corrections
                if any(t in c.get("tags", []) for t in tags)
            ]

        return corrections[-limit:]

    def get_insights(
        self,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get stored insights, optionally filtered.

        Args:
            category: Filter by category.
            tags: Filter by tags.
            limit: Maximum results.

        Returns:
            List of insight records.
        """
        insights = self._load_insights()

        if category:
            insights = [i for i in insights if i.get("category") == category]
        if tags:
            insights = [
                i for i in insights
                if any(t in i.get("tags", []) for t in tags)
            ]

        return insights[-limit:]

    def get_relevant_memories(
        self,
        query: str,
        issue_type: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Get all relevant memories for a query.

        Args:
            query: Search query.
            issue_type: Filter by issue type.

        Returns:
            Dictionary with corrections and insights.
        """
        tags = [issue_type] if issue_type else None
        query_lower = query.lower()

        # Filter corrections by query relevance
        corrections = self.get_corrections(tags=tags, limit=50)
        relevant_corrections = [
            c for c in corrections
            if query_lower in c.get("original", "").lower()
            or query_lower in c.get("correction", "").lower()
            or query_lower in c.get("context", "").lower()
        ][:5]

        # Filter insights by query relevance
        insights = self.get_insights(tags=tags, limit=50)
        relevant_insights = [
            i for i in insights
            if query_lower in i.get("insight", "").lower()
        ][:5]

        return {
            "corrections": relevant_corrections,
            "insights": relevant_insights,
        }

    def _load_corrections(self) -> list[dict[str, Any]]:
        """Load corrections from file."""
        if self._corrections_file.exists():
            try:
                with open(self._corrections_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _save_corrections(self, corrections: list[dict[str, Any]]) -> None:
        """Save corrections to file."""
        with open(self._corrections_file, "w", encoding="utf-8") as f:
            json.dump(corrections, f, ensure_ascii=False, indent=2)

    def _load_insights(self) -> list[dict[str, Any]]:
        """Load insights from file."""
        if self._insights_file.exists():
            try:
                with open(self._insights_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _save_insights(self, insights: list[dict[str, Any]]) -> None:
        """Save insights to file."""
        with open(self._insights_file, "w", encoding="utf-8") as f:
            json.dump(insights, f, ensure_ascii=False, indent=2)
