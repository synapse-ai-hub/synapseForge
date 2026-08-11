"""Wrapper para base de datos vectorial (ChromaDB).

Abstrae las operaciones de ChromaDB detrás de una interfaz simple.
Si en el futuro se cambia a pgvector u otro motor, solo se modifica este archivo.

Typical usage::

    from backend.agent.utils.vector_db import VectorDB

    db = VectorDB()
    db.create_collection("manual-producto")
    db.add_documents("manual-producto", ids=["c1"], documents=["texto..."], metadatas=[{"source": "doc.pdf"}])
    results = db.query("manual-producto", "¿cómo se instala?")
"""

import logging
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from backend.agent.utils.config_dir import get_knowledge_dir

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "all-mpnet-base-v2"


class VectorDB:
    """Wrapper para operaciones vectoriales con ChromaDB.

    Attributes:
        chroma_path: Ruta absoluta al directorio persistente de Chroma.
        embed_func: Función de embedding (SentenceTransformer).
        _client: Instancia de ``chromadb.PersistentClient``.
    """

    def __init__(self, collection_name: str | None = None) -> None:
        """Inicializa el cliente ChromaDB persistente.

        Args:
            collection_name: Si se pasa, crea/obtiene automáticamente
                esa colección y la deja como ``self.collection``.
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
                metadata={"embedding_model": _DEFAULT_MODEL},
            )

        logger.info(
            "VectorDB listo en %s (modelo: %s)",
            self.chroma_path,
            _DEFAULT_MODEL,
        )

    # ── Gestión de colecciones ──────────────────────────────────────

    def create_collection(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> chromadb.Collection:
        """Crea una nueva colección vectorial.

        Args:
            name: Nombre único de la colección.
            metadata: Metadatos opcionales (embedding_model, descripción, etc.).

        Returns:
            La instancia de la colección creada.

        Raises:
            ValueError: Si la colección ya existe.
        """
        meta = metadata or {}
        meta.setdefault("embedding_model", _DEFAULT_MODEL)

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
        """Obtiene una colección existente.

        Args:
            name: Nombre de la colección.

        Returns:
            La colección.

        Raises:
            ValueError: Si no existe.
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
        """Obtiene o crea una colección (idempotente).

        Args:
            name: Nombre de la colección.
            metadata: Metadatos usados solo si se crea.

        Returns:
            La colección.
        """
        meta = metadata or {}
        meta.setdefault("embedding_model", _DEFAULT_MODEL)

        col = self._client.get_or_create_collection(
            name=name,
            embedding_function=self.embed_func,
            metadata=meta,
        )
        logger.info("Colección '%s' lista.", name)
        return col

    def list_collections(self) -> list[dict[str, Any]]:
        """Lista todas las colecciones disponibles.

        Returns:
            Lista de dicts con ``name`` y ``metadata`` de cada colección.
        """
        collections = self._client.list_collections()
        return [
            {"name": c.name, "metadata": c.metadata}
            for c in collections
        ]

    def delete_collection(self, name: str) -> None:
        """Elimina una colección y todos sus datos.

        Args:
            name: Nombre de la colección a eliminar.
        """
        try:
            self._client.delete_collection(name)
            logger.info("Colección '%s' eliminada.", name)
        except (ValueError, chromadb.errors.NotFoundError):
            logger.warning("Colección '%s' no existe.", name)

    def get_collection_info(self, name: str) -> dict[str, Any]:
        """Obtiene información detallada de una colección.

        Args:
            name: Nombre de la colección.

        Returns:
            Dict con ``name``, ``metadata`` y ``count`` (cantidad de docs).
        """
        col = self.get_collection(name)
        count = col.count()
        return {
            "name": col.name,
            "metadata": col.metadata,
            "count": count,
        }

    # ── Operaciones CRUD ───────────────────────────────────────────

    def add_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Agrega documentos a una colección.

        Args:
            collection_name: Colección destino.
            ids: Lista de IDs únicos (strings).
            documents: Lista de textos a indexar.
            metadatas: Lista de metadatos por documento.
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
        """Actualiza documentos existentes.

        Args:
            collection_name: Colección.
            ids: IDs a actualizar.
            documents: Nuevos textos (None = mantener).
            metadatas: Nuevos metadatos (None = mantener).
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
        """Elimina documentos por ID.

        Args:
            collection_name: Colección.
            ids: IDs a eliminar.
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
        """Obtiene documentos por ID o filtro.

        Args:
            collection_name: Colección.
            ids: Lista opcional de IDs.
            where: Filtro opcional de metadatos.
            limit: Máximo de resultados.
            offset: Desplazamiento.

        Returns:
            Dict con ``ids``, ``documents``, ``metadatas``.
        """
        col = self.get_collection(collection_name)
        return col.get(
            ids=ids,
            where=where,
            limit=limit,
            offset=offset,
        )

    # ── Búsqueda ────────────────────────────────────────────────────

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Busca los chunks más similares a un texto.

        Args:
            collection_name: Colección donde buscar.
            query_text: Texto de consulta en lenguaje natural.
            n_results: Cantidad de resultados a retornar (default 10).
            where: Filtro opcional de metadatos.

        Returns:
            Dict con ``ids``, ``documents``, ``metadatas``, ``distances``.
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
        """Busca por vector de embedding directamente.

        Args:
            collection_name: Colección.
            embedding: Vector precomputado.
            n_results: Cantidad de resultados.
            where: Filtro opcional.

        Returns:
            Dict con ``ids``, ``documents``, ``metadatas``, ``distances``.
        """
        col = self.get_collection(collection_name)
        return col.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
