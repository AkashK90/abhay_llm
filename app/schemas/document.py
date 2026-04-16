from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    document_id: str
    job_id: str
    original_filename: str
    file_size_bytes: int
    status: str
    message: str = "Document uploaded successfully. Ingestion has started."


class BatchDocumentUploadResponse(BaseModel):
    total_uploaded: int
    uploads: list[DocumentUploadResponse]


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    page_count: int | None = None
    chunk_count: int = 0
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentChunkSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chunk_index: int
    page_number: int | None = None
    char_offset: int
    text_preview: str
    token_count: int
    chroma_id: str
    created_at: datetime


class DocumentDetail(DocumentMetadata):
    filename: str
    file_path: str
    chunks: list[DocumentChunkSchema] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentMetadata]


class JobStatusResponse(BaseModel):
    job_id: str
    document_id: str
    celery_task_id: str | None = None
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
