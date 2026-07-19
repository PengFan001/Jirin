"""Base exporter class.

All exporters inherit from this base class which provides common
functionality for reading knowledge and building export content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jirin.core.context import ExecutionContext


class BaseExporter:
    """Base class for skill/plugin exporters.

    Provides:
    - Knowledge base reading
    - Agent prompt extraction
    - Output directory management
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self.context = ExecutionContext(config_path=config_path)

    def _read_static_knowledge(self) -> dict[str, str]:
        """Read all static knowledge documents (including subdirectories).

        Returns:
            Dictionary mapping relative path to content.
        """
        km = self.context.knowledge_manager
        static_dir = Path(km._static_dir) if hasattr(km, '_static_dir') else Path("src/jirin/knowledge/static")

        docs = {}
        if static_dir.exists():
            for md_file in static_dir.rglob("*.md"):
                # Use relative path as key to preserve directory structure
                rel_key = str(md_file.relative_to(static_dir))
                docs[rel_key] = md_file.read_text(encoding="utf-8")
                # Also store by filename for backward compatibility
                docs[md_file.name] = docs[rel_key]

        return docs

    def _get_agent_prompts(self) -> dict[str, str]:
        """Get system prompts from all agents.

        Returns:
            Dictionary mapping agent name to system prompt.
        """
        from jirin.agents.je_agent import JEAgent
        from jirin.agents.anr_agent import ANRAgent
        from jirin.agents.ne_agent import NEAgent
        from jirin.agents.summary_agent import SUMMARY_SYSTEM_PROMPT

        return {
            "je_agent": JEAgent(self.context).get_system_prompt(),
            "anr_agent": ANRAgent(self.context).get_system_prompt(),
            "ne_agent": NEAgent(self.context).get_system_prompt(),
            "summary_agent": SUMMARY_SYSTEM_PROMPT,
        }

    def _ensure_output_dir(self, output_dir: Path) -> None:
        """Ensure output directory exists.

        Args:
            output_dir: Target directory.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
