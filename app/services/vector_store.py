"""
vector_store.py
Thin wrapper around ChromaDB HTTP client.
Handles upsert, similarity search, and deletion.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chroma_id: str
    document_id: str
    chunk_index: int
    page_number: int | None
    text: str
    distance: float
    score: float  # 1 - distance, higher = more relevant


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection_name = settings.chroma_collection
        self._collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        return self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Upsert a batch of chunk embeddings into ChromaDB."""
        if not ids:
            return
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug("Upserted %d chunks into ChromaDB", len(ids))

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        """
        Perform cosine similarity search.
        Optionally filter to specific document_ids.
        If document_ids is empty or None, searches across all documents.
        """
        where: dict | None = None
        
        # Only apply filter if document_ids is provided and non-empty
        if document_ids and len(document_ids) > 0:
            # Filter out any invalid placeholder values like "string"
            valid_ids = [id for id in document_ids if id and id != "string" and id.strip()]
            if valid_ids:
                if len(valid_ids) == 1:
                    where = {"document_id": {"$eq": valid_ids[0]}}
                else:
                    where = {"document_id": {"$in": valid_ids}}

        count = self._count()
        if count == 0:
            logger.warning("ChromaDB collection is empty, no vectors to search")
            return []

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[RetrievedChunk] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for chroma_id, text, meta, dist in zip(ids, docs, metas, distances):
            chunks.append(
                RetrievedChunk(
                    chroma_id=chroma_id,
                    document_id=meta.get("document_id", ""),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    page_number=meta.get("page_number"),
                    text=text,
                    distance=dist,
                    score=round(1.0 - dist, 4),
                )
            )

        if chunks:
            logger.info("[VectorStore] Retrieved %d chunks (filter: %s)", len(chunks), where)
        else:
            logger.warning("[VectorStore] No chunks retrieved with filter: %s", where)
            
        return chunks

    def delete_document(self, document_id: str) -> int:
        """Delete all chunks belonging to a document. Returns count deleted."""
        results = self._collection.get(where={"document_id": {"$eq": document_id}})
        ids = results.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
            logger.info("Deleted %d vectors for document_id=%s", len(ids), document_id)
        return len(ids)

    def _count(self) -> int:
        try:
            return self._collection.count()
        except Exception:
            return 0


# Module-level singleton
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
