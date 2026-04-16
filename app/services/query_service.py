"""
query_service.py
Full RAG query pipeline:
  1. Embed the user question (Gemini)
  2. Retrieve top-K chunks (ChromaDB)
  3. Generate an answer (Gemini LLM)
  4. Return answer + source references
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.document import Document
import app.services.embedding_service as embedding_service_module
import app.services.llm_service as llm_service_module
import app.services.vector_store as vector_store_module
from app.services.vector_store import RetrievedChunk

logger = logging.getLogger(__name__)


def get_embedding_service():
    return embedding_service_module.get_embedding_service()


def get_vector_store():
    return vector_store_module.get_vector_store()


def get_llm_service():
    return llm_service_module.get_llm_service()


@dataclass
class SourceReference:
    document_id: str
    document_name: str
    chunk_index: int
    page_number: int | None
    relevance_score: float
    text_preview: str


@dataclass
class QueryResult:
    question: str
    answer: str
    sources: list[SourceReference]
    chunks_retrieved: int
    model_used: str


def answer_question(
    question: str,
    db: Session,
    document_ids: list[str] | None = None,
    top_k: int | None = None,
) -> QueryResult:
    """
    Full RAG pipeline execution.

    Args:
        question: The user's question string.
        db: SQLAlchemy session for metadata lookups.
        document_ids: Optional list to restrict retrieval to specific documents.
                      If None or empty, searches across all documents.

    Returns:
        QueryResult with answer text and source citations.
    """
    settings = get_settings()

    if not question.strip():
        raise ValueError("Question cannot be empty")

    # ── Step 1: Embed question ────────────────────────────────────────────────
    logger.info("[Query] Embedding question (%d chars)", len(question))
    embedding_svc = get_embedding_service()
    query_embedding = embedding_svc.embed_text(question)
    logger.debug("[Query] Question embedding dimension: %d", len(query_embedding))

    # ── Step 2: Retrieve relevant chunks ─────────────────────────────────────
    vector_store = get_vector_store()
    retrieval_top_k = top_k or settings.retrieval_top_k
    
    # Filter out invalid document_ids
    valid_doc_ids = None
    if document_ids and len(document_ids) > 0:
        valid_doc_ids = [id for id in document_ids if id and id != "string" and id.strip()]
    
    logger.info(
        "[Query] Searching with document_ids=%s, top_k=%d",
        valid_doc_ids if valid_doc_ids else "all",
        retrieval_top_k,
    )
    
    retrieved: list[RetrievedChunk] = vector_store.similarity_search(
        query_embedding=query_embedding,
        top_k=retrieval_top_k,
        document_ids=valid_doc_ids,
    )

    if not retrieved:
        logger.warning("[Query] No relevant chunks found for question: %s", question)
        return QueryResult(
            question=question,
            answer="I could not find any relevant content in the uploaded documents to answer your question.",
            sources=[],
            chunks_retrieved=0,
            model_used=settings.gemini_llm_model,
        )

    logger.info("[Query] Retrieved %d chunks from vector store", len(retrieved))

    # ── Step 3: Fetch document names for citation ─────────────────────────────
    doc_id_to_name = _fetch_document_names(
        db, list({c.document_id for c in retrieved})
    )

    # ── Step 4: Generate answer ───────────────────────────────────────────────
    context_texts = [chunk.text for chunk in retrieved]
    llm_svc = get_llm_service()
    answer = llm_svc.generate_answer(question=question, context_chunks=context_texts)

    # ── Step 5: Build source citations ────────────────────────────────────────
    sources = [
        SourceReference(
            document_id=chunk.document_id,
            document_name=doc_id_to_name.get(chunk.document_id, "Unknown document"),
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            relevance_score=chunk.score,
            text_preview=chunk.text[:300],
        )
        for chunk in retrieved
    ]

    return QueryResult(
        question=question,
        answer=answer,
        sources=sources,
        chunks_retrieved=len(retrieved),
        model_used=settings.gemini_llm_model,
    )


def _fetch_document_names(db: Session, document_ids: list[str]) -> dict[str, str]:
    """Return a mapping of document_id → original_filename."""
    if not document_ids:
        return {}
    docs = db.query(Document).filter(Document.id.in_(document_ids)).all()
    return {d.id: d.original_filename for d in docs}
