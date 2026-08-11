"""Wrapper for the vector database (ChromaDB).

Abstracts ChromaDB operations behind a simple interface. If the engine is
switched later (e.g. pgvector), only this file needs to change.

The embedding model (SentenceTransformer) is loaded once at initialization
and kept in memory to avoid per-operation reload latency.

Typical usage::

    from backend.agent.utils.vector_db import VectorDB

    db = VectorDB()
    db.create_collection("manual-producto")
    db.add_documents("manual-producto", ids=["c1"], documents=["texto..."], metadatas=[{"source": "doc.pdf"}])
    results = db.query("manual-producto", "¿cómo se instala?")
"""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from backend.agent.utils.config_dir import get_knowledge_dir

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "all-MiniLM-L6-v2"


class VectorDB:
    """ChromaDB vector operations wrapper.

    Attributes:
        chroma_path: Absolute path to the persistent Chroma directory.
        embed_func: Embedding function (SentenceTransformer), loaded once at init.
        _client: ``chromadb.PersistentClient`` instance.
    """

    def __init__(self, collection_name: str | None = None) -> None:
        """Initialize the persistent ChromaDB client and the embedding model.

        Args:
            collection_name: If provided, creates/gets that collection and
                stores it as ``self.collection``.
        """
        self.chroma_path = get_knowledge_dir()
        self.chroma_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(self.chroma_path))

        self.embed_func = SentenceTransformerEmbeddingFunction(
            model_name=_DEFAULT_MODEL,
            device="cpu",
        )

        self.collection = None
        if collection_name:
            self.collection = self._client.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embed_func,
                metadata={"embedding_model": _DEFAULT_MODEL, "hnsw:space": "cosine"},
            )

        logger.info(
            "VectorDB listo en %s (modelo: %s)",
            self.chroma_path,
            _DEFAULT_MODEL,
        )

    # ── Collection management ────────────────────────────────────────────

    def create_collection(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> chromadb.Collection:
        """Create a new vector collection.

        Args:
            name: Unique collection name.
            metadata: Optional metadata (embedding_model, description, etc.).

        Returns:
            The created collection instance.

        Raises:
            ValueError: If the collection already exists.
        """
        meta = metadata or {}
        meta.setdefault("embedding_model", _DEFAULT_MODEL)
        meta.setdefault("hnsw:space", "cosine")

        try:
            col = self._client.create_collection(
                name=name,
                embedding_function=self.embed_func,
                metadata=meta,
            )
            logger.info("Colección '%s' creada.", name)
            return col
        except ValueError:
            logger.warning("Colección '%s' ya existe.", name)
            raise

    def get_collection(self, name: str) -> chromadb.Collection:
        """Get an existing collection.

        Args:
            name: Name of the collection.

        Returns:
            The collection.

        Raises:
            ValueError: If the collection does not exist.
        """
        return self._client.get_collection(
            name=name,
            embedding_function=self.embed_func,
        )

    def get_or_create_collection(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> chromadb.Collection:
        """Get or create a collection (idempotent).

        Args:
            name: Name of the collection.
            metadata: Metadata used only if the collection is created.

        Returns:
            The collection.
        """
        meta = metadata or {}
        meta.setdefault("embedding_model", _DEFAULT_MODEL)
        meta.setdefault("hnsw:space", "cosine")

        col = self._client.get_or_create_collection(
            name=name,
            embedding_function=self.embed_func,
            metadata=meta,
        )
        logger.info("Colección '%s' lista.", name)
        return col

    def list_collections(self) -> list[dict[str, Any]]:
        """List all available collections.

        Returns:
            List of dicts with ``name`` and ``metadata`` per collection.
        """
        collections = self._client.list_collections()
        return [
            {"name": c.name, "metadata": c.metadata}
            for c in collections
        ]

    def delete_collection(self, name: str) -> None:
        """Delete a collection and all its data.

        Args:
            name: Name of the collection to delete.
        """
        try:
            self._client.delete_collection(name)
            logger.info("Colección '%s' eliminada.", name)
        except (ValueError, chromadb.errors.NotFoundError):
            logger.warning("Colección '%s' no existe.", name)

    def get_collection_info(self, name: str) -> dict[str, Any]:
        """Get detailed info of a collection.

        Args:
            name: Name of the collection.

        Returns:
            Dict with ``name``, ``metadata`` and ``count`` (docs count).
        """
        col = self.get_collection(name)
        count = col.count()
        return {
            "name": col.name,
            "metadata": col.metadata,
            "count": count,
        }

    # ── CRUD operations ─────────────────────────────────────────────────

    def add_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add documents to a collection.

        Args:
            collection_name: Target collection.
            ids: List of unique IDs (strings).
            documents: List of texts to index.
            metadatas: Optional metadata per document.
        """
        col = self.get_collection(collection_name)
        col.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(
            "%d documento(s) agregados a '%s'.",
            len(ids),
            collection_name,
        )

    def update_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Update existing documents.

        Args:
            collection_name: Collection.
            ids: IDs to update.
            documents: New texts (None = keep).
            metadatas: New metadata (None = keep).
        """
        col = self.get_collection(collection_name)
        col.update(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(
            "%d documento(s) actualizados en '%s'.",
            len(ids),
            collection_name,
        )

    def delete_documents(
        self,
        collection_name: str,
        ids: list[str],
    ) -> None:
        """Delete documents by ID.

        Args:
            collection_name: Collection.
            ids: IDs to delete.
        """
        col = self.get_collection(collection_name)
        col.delete(ids=ids)
        logger.info(
            "%d documento(s) eliminados de '%s'.",
            len(ids),
            collection_name,
        )

    def get_documents(
        self,
        collection_name: str,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Get documents by ID or filter.

        Args:
            collection_name: Collection.
            ids: Optional list of IDs.
            where: Optional metadata filter.
            limit: Maximum results.
            offset: Offset.

        Returns:
            Dict with ``ids``, ``documents``, ``metadatas``.
        """
        col = self.get_collection(collection_name)
        return col.get(
            ids=ids,
            where=where,
            limit=limit,
            offset=offset,
        )

    # ── Search ──────────────────────────────────────────────────────────

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Find the most similar chunks to a text.

        Args:
            collection_name: Collection to search.
            query_text: Natural language query.
            n_results: Number of results to return (default 10).
            where: Optional metadata filter.

        Returns:
            Dict with ``ids``, ``documents``, ``metadatas``, ``distances``.
        """
        col = self.get_collection(collection_name)
        return col.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    def query_by_embedding(
        self,
        collection_name: str,
        embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search directly by an embedding vector.

        Args:
            collection_name: Collection.
            embedding: Precomputed vector.
            n_results: Number of results.
            where: Optional filter.

        Returns:
            Dict with ``ids``, ``documents``, ``metadatas``, ``distances``.
        """
        col = self.get_collection(collection_name)
        return col.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )


_db_singleton: VectorDB | None = None


def get_vector_db() -> VectorDB:
    """Return the process-wide shared VectorDB instance.

    The embedding model is loaded once (pre-loaded at app startup via
    ``main.py``) and shared by every consumer (RAG routes, the ``rag`` tool
    and the AgentInfo listing). It is never killed, so the first use of RAG
    does not pay the model-load cost.

    Returns:
        The shared VectorDB instance.
    """
    global _db_singleton
    if _db_singleton is None:
        _db_singleton = VectorDB()
    return _db_singleton
