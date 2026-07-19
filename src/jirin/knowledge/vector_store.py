"""Vector store for semantic knowledge retrieval.

Uses ChromaDB for local embedded vector storage and similarity search.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings


class VectorStore:
    """ChromaDB-based vector store for knowledge retrieval.

    Supports:
    - Static knowledge documents (principles, analysis flows)
    - Dynamic case embeddings (learned from past analyses)
    - Similarity search with configurable thresholds
    """

    def __init__(
        self,
        persist_dir: str = "data/vector_db",
        embedding_config: dict[str, Any] | None = None,
    ) -> None:
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._embedding_config = embedding_config or {}
        self._client: chromadb.ClientAPI | None = None
        self._collections: dict[str, Any] = {}

    @property
    def client(self) -> chromadb.ClientAPI:
        """Lazy-initialized ChromaDB client."""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=str(self._persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    def get_or_create_collection(self, name: str) -> Any:
        """Get or create a ChromaDB collection.

        Args:
            name: Collection name (e.g., "static_knowledge", "cases").

        Returns:
            ChromaDB collection object.
        """
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add documents to a collection.

        Args:
            collection_name: Target collection name.
            documents: List of text documents to embed and store.
            ids: Unique IDs for each document.
            metadatas: Optional metadata for each document.
        """
        collection = self.get_or_create_collection(collection_name)
        collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas,
        )

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar documents.

        Args:
            collection_name: Collection to search in.
            query: Query text for similarity search.
            top_k: Number of results to return.
            where: Optional metadata filter.

        Returns:
            List of matching documents with scores.
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            if collection.count() == 0:
                return []

            kwargs: dict[str, Any] = {
                "query_texts": [query],
                "n_results": min(top_k, collection.count()),
            }
            if where:
                kwargs["where"] = where

            results = collection.query(**kwargs)

            # Format results
            formatted = []
            if results and results["documents"]:
                docs = results["documents"][0]
                metas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]
                ids_list = results.get("ids", [[]])[0]

                for i, doc in enumerate(docs):
                    formatted.append({
                        "id": ids_list[i] if i < len(ids_list) else "",
                        "document": doc,
                        "metadata": metas[i] if i < len(metas) else {},
                        "distance": distances[i] if i < len(distances) else 0.0,
                        "similarity": 1.0 - (distances[i] if i < len(distances) else 1.0),
                    })

            return formatted

        except Exception:
            return []

    def delete_document(self, collection_name: str, doc_id: str) -> None:
        """Delete a document from a collection.

        Args:
            collection_name: Collection name.
            doc_id: Document ID to delete.
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            collection.delete(ids=[doc_id])
        except Exception:
            pass

    def get_collection_count(self, collection_name: str) -> int:
        """Get the number of documents in a collection.

        Args:
            collection_name: Collection name.

        Returns:
            Number of documents.
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            return collection.count()
        except Exception:
            return 0
