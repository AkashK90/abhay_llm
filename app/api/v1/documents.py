"""
documents.py
REST endpoints for document management.

POST   /api/v1/documents/upload       Upload a new document
GET    /api/v1/documents              List all documents
GET    /api/v1/documents/{id}         Document detail + chunk metadata
DELETE /api/v1/documents/{id}         Remove document and its vectors
GET    /api/v1/jobs/{job_id}          Ingestion job status
"""
from fastapi import APIRouter, UploadFile, File, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.job import IngestionJob
from app.schemas.document import (
    DocumentUploadResponse,
    BatchDocumentUploadResponse,
    DocumentListResponse,
    DocumentMetadata,
    DocumentDetail,
    DocumentChunkSchema,
    JobStatusResponse,
)
from app.services.document_service import (
    save_uploads_and_enqueue,
    get_document,
    list_documents,
    delete_document,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload-multiple",
    response_model=BatchDocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload multiple documents for ingestion",
)
async def upload_documents_batch(
    files: list[UploadFile] = File(..., description="Upload multiple files (PDF, DOCX, TXT, MD)"),
    db: Session = Depends(get_db),
):
    results = save_uploads_and_enqueue(files, db)
    uploads = [
        DocumentUploadResponse(
            document_id=document.id,
            job_id=job.id,
            original_filename=document.original_filename,
            file_size_bytes=document.file_size_bytes,
            status=document.status,
        )
        for document, job in results
    ]
    return BatchDocumentUploadResponse(
        total_uploaded=len(uploads),
        uploads=uploads,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List all uploaded documents",
)
def get_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return paginated list of documents with their ingestion status."""
    docs = list_documents(db, skip=skip, limit=limit)
    return DocumentListResponse(
        total=len(docs),
        documents=[DocumentMetadata.model_validate(d) for d in docs],
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    summary="Get document detail and chunk metadata",
)
def get_document_detail(
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Returns full document metadata and a list of its processed chunks.
    Chunks are only present after status = `completed`.
    """
    doc = get_document(document_id, db)
    chunks = [DocumentChunkSchema.model_validate(c) for c in doc.chunks]
    detail = DocumentDetail.model_validate(doc)
    detail.chunks = chunks
    return detail


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and all its data",
)
def remove_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Permanently deletes the document file, its vector embeddings in ChromaDB,
    and all related database records.
    """
    delete_document(document_id, db)
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


# ── Job status endpoint (lives under /jobs prefix, registered in main.py) ────

job_router = APIRouter(prefix="/jobs", tags=["Jobs"])


@job_router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get ingestion job status",
)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Poll this endpoint after uploading a document to track ingestion progress.
    Status values: `pending` → `processing` → `completed` | `failed`
    """
    from fastapi import HTTPException

    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        document_id=job.document_id,
        celery_task_id=job.celery_task_id,
        status=job.status,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
    )
