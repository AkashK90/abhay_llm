"""
document_service.py
Handles upload logic: save file, create DB records, enqueue Celery task.
"""
from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import Path

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.document import Document
from app.db.models.job import IngestionJob
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}


def save_upload_and_enqueue(
    file: UploadFile,
    db: Session,
) -> tuple[Document, IngestionJob]:
    """
    1. Validate file
    2. Save to local storage
    3. Create Document + IngestionJob rows
    4. Enqueue Celery ingestion task
    Returns (document, job)
    """
    settings = get_settings()
    _validate_document_limit(db, settings.max_documents)
    _validate_file(file)

    doc_id = str(uuid.uuid4())
    suffix = Path(file.filename or "upload").suffix.lower()
    stored_filename = f"{doc_id}{suffix}"
    file_path = Path(settings.storage_dir) / stored_filename

    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Stream to disk
    file_size = _write_file(file, file_path, settings.max_file_size_mb)

    mime_type = _resolve_mime(file.content_type, suffix)

    # Persist document record
    document = Document(
        id=doc_id,
        filename=stored_filename,
        original_filename=file.filename or "upload",
        file_path=str(file_path),
        file_size_bytes=file_size,
        mime_type=mime_type,
        status="pending",
    )
    db.add(document)

    job = IngestionJob(document_id=doc_id, status="pending")
    db.add(job)
    db.commit()
    db.refresh(document)
    db.refresh(job)

    # Enqueue — imported here to avoid circular deps at module load time
    from app.workers.tasks.ingestion import ingest_document_task

    celery_result = ingest_document_task.delay(
        document_id=doc_id,
        file_path=str(file_path),
        mime_type=mime_type,
        job_id=job.id,
    )

    job.celery_task_id = celery_result.id
    db.commit()

    logger.info("Enqueued ingestion task %s for document %s", celery_result.id, doc_id)
    return document, job


def save_uploads_and_enqueue(
    files: list[UploadFile],
    db: Session,
) -> list[tuple[Document, IngestionJob]]:
    settings = get_settings()
    if not files:
        raise HTTPException(status_code=422, detail="At least one file is required")

    current_count = db.query(Document).count()
    if current_count + len(files) > settings.max_documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Uploading {len(files)} file(s) would exceed max documents "
                f"limit ({settings.max_documents})."
            ),
        )

    for file in files:
        _validate_file(file)

    results: list[tuple[Document, IngestionJob]] = []
    for file in files:
        results.append(save_upload_and_enqueue(file, db))
    return results


def get_document(document_id: str, db: Session) -> Document:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


def list_documents(db: Session, skip: int = 0, limit: int = 50) -> list[Document]:
    return db.query(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit).all()


def delete_document(document_id: str, db: Session) -> None:
    doc = get_document(document_id, db)

    # Remove vectors from ChromaDB
    try:
        get_vector_store().delete_document(document_id)
    except Exception as exc:
        logger.warning("Failed to delete vectors for %s: %s", document_id, exc)

    # Remove file from disk
    try:
        Path(doc.file_path).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Failed to delete file %s: %s", doc.file_path, exc)

    db.delete(doc)
    db.commit()
    logger.info("Deleted document %s", document_id)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validate_document_limit(db: Session, max_docs: int) -> None:
    count = db.query(Document).count()
    if count >= max_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document limit reached ({max_docs}). Delete documents before uploading more.",
        )


def _validate_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=422, detail="Filename is required")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )


def _write_file(file: UploadFile, dest: Path, max_size_mb: int) -> int:
    max_bytes = max_size_mb * 1024 * 1024
    total = 0
    try:
        with open(dest, "wb") as f:
            while chunk := file.file.read(1024 * 1024):  # 1 MB chunks
                f.write(chunk)
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds max size of {max_size_mb} MB",
                    )
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return total


def _resolve_mime(content_type: str | None, suffix: str) -> str:
    if content_type and content_type in ALLOWED_MIME_TYPES:
        return content_type
    guessed, _ = mimetypes.guess_type(f"file{suffix}")
    return guessed or "application/octet-stream"
