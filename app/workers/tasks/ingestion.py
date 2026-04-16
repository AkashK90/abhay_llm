from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.db.models.document import Document, DocumentChunk
from app.db.models.job import IngestionJob
from app.db.session import SessionLocal
from app.services.embedding_service import get_embedding_service
from app.services.vector_store import get_vector_store
from app.workers.celery_app import celery_app
from ingestion.pipeline import run_ingestion_pipeline

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.ingestion.ingest_document_task",
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def ingest_document_task(
    self,
    document_id: str,
    file_path: str,
    mime_type: str,
    job_id: str,
) -> dict:
    settings = get_settings()
    db = SessionLocal()

    try:
        document = db.get(Document, document_id)
        job = db.get(IngestionJob, job_id)
        if not document or not job:
            raise ValueError("Document or job record not found")

        document.status = "processing"
        document.error_message = None
        job.status = "processing"
        job.error_message = None
        job.started_at = _utcnow()
        db.commit()

        pipeline_result = run_ingestion_pipeline(
            document_id=document_id,
            file_path=file_path,
            mime_type=mime_type,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        if pipeline_result.page_count > 1000:
            raise ValueError("Document exceeds max page limit (1000)")

        if not pipeline_result.chunks:
            raise ValueError("No text chunks produced. The document may be empty or scanned.")

        text_chunks = [chunk.text for chunk in pipeline_result.chunks]
        embeddings = get_embedding_service().embed_batch(text_chunks)

        vector_store = get_vector_store()
        vector_store.delete_document(document_id)
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete(
            synchronize_session=False
        )

        ids = [chunk.id for chunk in pipeline_result.chunks]
        metadatas = [
            {
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "char_offset": chunk.char_offset,
            }
            for chunk in pipeline_result.chunks
        ]

        vector_store.upsert_chunks(
            ids=ids,
            embeddings=embeddings,
            documents=text_chunks,
            metadatas=metadatas,
        )

        db.add_all(
            [
                DocumentChunk(
                    id=chunk.id,
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    char_offset=chunk.char_offset,
                    text_preview=chunk.text_preview,
                    token_count=chunk.token_estimate,
                    chroma_id=chunk.id,
                )
                for chunk in pipeline_result.chunks
            ]
        )

        document.page_count = pipeline_result.page_count
        document.chunk_count = pipeline_result.chunk_count
        document.status = "completed"
        document.updated_at = _utcnow()
        job.status = "completed"
        job.completed_at = _utcnow()
        db.commit()

        logger.info(
            "Ingestion completed for document_id=%s chunks=%d",
            document_id,
            pipeline_result.chunk_count,
        )
        return {
            "document_id": document_id,
            "job_id": job_id,
            "status": "completed",
            "page_count": pipeline_result.page_count,
            "chunk_count": pipeline_result.chunk_count,
        }

    except Exception as exc:
        logger.exception("Ingestion failed for document_id=%s: %s", document_id, exc)
        db.rollback()
        _mark_failed(db, document_id, job_id, str(exc))
        raise
    finally:
        db.close()


def _mark_failed(db, document_id: str, job_id: str, error_message: str) -> None:
    document = db.get(Document, document_id)
    job = db.get(IngestionJob, job_id)

    if document:
        document.status = "failed"
        document.error_message = error_message[:4000]
        document.updated_at = _utcnow()
    if job:
        job.status = "failed"
        job.error_message = error_message[:4000]
        job.completed_at = _utcnow()

    db.commit()
