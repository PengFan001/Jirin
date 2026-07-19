"""Execution context management.

Provides runtime configuration and shared resources to agents.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 12):
    import tomllib
else:
    import tomli as tomllib

from jirin.knowledge.manager import KnowledgeManager
from jirin.knowledge.vector_store import VectorStore
from jirin.knowledge.case_store import CaseStore


class ExecutionContext:
    """Runtime context shared across all agents.

    Holds configuration, knowledge manager, and storage references
    that agents need during analysis.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._config: dict[str, Any] = {}
        self._config_missing: str | None = None
        self._knowledge_manager: KnowledgeManager | None = None
        self._vector_store: VectorStore | None = None
        self._case_store: CaseStore | None = None

        if config_path:
            self.load_config(config_path)

    @property
    def config_missing(self) -> bool:
        """Whether the configuration file was not found."""
        return self._config_missing is not None

    @property
    def config_missing_path(self) -> str | None:
        """Path of the missing configuration file (for display)."""
        return self._config_missing

    def load_config(self, config_path: str | Path) -> None:
        """Load configuration from TOML file.

        If the file does not exist, use empty config and record a warning
        so that the CLI layer can print a user-friendly message.
        """
        path = Path(config_path)
        if not path.exists():
            self._config_missing = str(path)
            return
        with open(path, "rb") as f:
            self._config = tomllib.load(f)

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    def get_llm_config(self) -> dict[str, Any]:
        """Get LLM configuration."""
        return self._config.get("llm", {})

    def get_embedding_config(self) -> dict[str, Any]:
        """Get embedding configuration."""
        return self._config.get("embedding", {})

    def get_knowledge_config(self) -> dict[str, Any]:
        """Get knowledge base configuration."""
        return self._config.get("knowledge", {})

    def get_storage_config(self) -> dict[str, Any]:
        """Get storage configuration."""
        return self._config.get("storage", {})

    def get_source_config(self) -> dict[str, Any]:
        """Get AOSP source code configuration."""
        return self._config.get("source", {})

    @property
    def knowledge_manager(self) -> KnowledgeManager:
        """Lazy-initialized knowledge manager."""
        if self._knowledge_manager is None:
            self._knowledge_manager = KnowledgeManager(
                static_dir=self.get_knowledge_config().get(
                    "static_dir", "src/jirin/knowledge/static"
                ),
                vector_store=self.vector_store,
                case_store=self.case_store,
            )
        return self._knowledge_manager

    @property
    def vector_store(self) -> VectorStore:
        """Lazy-initialized vector store."""
        if self._vector_store is None:
            storage_cfg = self.get_storage_config()
            self._vector_store = VectorStore(
                persist_dir=storage_cfg.get("vector_db_dir", ".jirin/vector_db"),
                embedding_config=self.get_embedding_config(),
            )
        return self._vector_store

    @property
    def case_store(self) -> CaseStore:
        """Lazy-initialized case store."""
        if self._case_store is None:
            storage_cfg = self.get_storage_config()
            self._case_store = CaseStore(
                cases_dir=storage_cfg.get("cases_dir", ".jirin/cases")
            )
        return self._case_store
