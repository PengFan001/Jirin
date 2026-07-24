"""Structured case store for historical analysis cases.

Stores analysis cases as JSON files with metadata for retrieval
and learning from past analyses.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class CaseStore:
    """JSON-based case storage for historical analysis records.

    Each case is stored as a JSON file with:
    - Unique ID
    - Issue type
    - Root cause
    - Analysis summary
    - Solution
    - Key features/patterns
    - Timestamp
    - User feedback (if any)
    """

    def __init__(self, cases_dir: str = ".jirin/cases") -> None:
        self._cases_dir = Path(cases_dir)
        self._cases_dir.mkdir(parents=True, exist_ok=True)

    def save_case(self, case_data: dict[str, Any]) -> str:
        """Save a new analysis case.

        Args:
            case_data: Case data including root_cause, issue_type, etc.

        Returns:
            Case ID.
        """
        case_id = case_data.get("id", str(uuid.uuid4())[:8])
        case_data["id"] = case_id
        case_data["created_at"] = case_data.get(
            "created_at", datetime.now().isoformat()
        )

        file_path = self._cases_dir / f"{case_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(case_data, f, ensure_ascii=False, indent=2)

        return case_id

    def load_case(self, case_id: str) -> dict[str, Any] | None:
        """Load a case by ID.

        Args:
            case_id: Case identifier.

        Returns:
            Case data or None if not found.
        """
        file_path = self._cases_dir / f"{case_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_cases(
        self,
        issue_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List cases with optional filtering.

        Args:
            issue_type: Filter by issue type (je/anr/ne).
            limit: Maximum number of cases to return.

        Returns:
            List of case data.
        """
        cases = []
        for file_path in sorted(self._cases_dir.glob("*.json"), reverse=True):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    case = json.load(f)
                if issue_type and case.get("issue_type") != issue_type:
                    continue
                cases.append(case)
                if len(cases) >= limit:
                    break
            except (json.JSONDecodeError, OSError):
                continue
        return cases

    def search_cases(
        self,
        query: str | None = None,
        issue_type: str | None = None,
        root_cause_keyword: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search cases by keyword or metadata.

        Args:
            query: Full-text search query.
            issue_type: Filter by issue type.
            root_cause_keyword: Search in root cause field.
            limit: Maximum results.

        Returns:
            Matching cases.
        """
        results = []
        for case in self.list_cases(issue_type=issue_type, limit=limit * 3):
            score = 0

            if query:
                query_lower = query.lower()
                # Search in key fields
                for field in ["root_cause", "analysis_summary", "solution", "log_excerpt"]:
                    value = str(case.get(field, "")).lower()
                    if query_lower in value:
                        score += 1

            if root_cause_keyword:
                keyword_lower = root_cause_keyword.lower()
                if keyword_lower in str(case.get("root_cause", "")).lower():
                    score += 2

            if score > 0 or (not query and not root_cause_keyword):
                case["_search_score"] = score
                results.append(case)

        # Sort by score descending
        results.sort(key=lambda x: x.get("_search_score", 0), reverse=True)
        return results[:limit]

    def update_case(self, case_id: str, updates: dict[str, Any]) -> bool:
        """Update an existing case.

        Args:
            case_id: Case identifier.
            updates: Fields to update.

        Returns:
            True if updated successfully.
        """
        case = self.load_case(case_id)
        if case is None:
            return False

        case.update(updates)
        case["updated_at"] = datetime.now().isoformat()

        file_path = self._cases_dir / f"{case_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(case, f, ensure_ascii=False, indent=2)

        return True

    def delete_case(self, case_id: str) -> bool:
        """Delete a case.

        Args:
            case_id: Case identifier.

        Returns:
            True if deleted.
        """
        file_path = self._cases_dir / f"{case_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def add_feedback(self, case_id: str, feedback: dict[str, Any]) -> bool:
        """Add user feedback to a case (for learning).

        Args:
            case_id: Case identifier.
            feedback: Feedback data (e.g., correction, rating).

        Returns:
            True if updated.
        """
        case = self.load_case(case_id)
        if case is None:
            return False

        if "feedback" not in case:
            case["feedback"] = []

        feedback["timestamp"] = datetime.now().isoformat()
        case["feedback"].append(feedback)
        case["has_feedback"] = True

        return self.update_case(case_id, case)

    def get_stats(self) -> dict[str, Any]:
        """Get case store statistics.

        Returns:
            Stats including total count, by type, with feedback.
        """
        all_cases = self.list_cases(limit=10000)
        stats = {
            "total": len(all_cases),
            "by_type": {},
            "with_feedback": 0,
        }
        for case in all_cases:
            issue_type = case.get("issue_type", "unknown")
            stats["by_type"][issue_type] = stats["by_type"].get(issue_type, 0) + 1
            if case.get("has_feedback"):
                stats["with_feedback"] += 1

        return stats
