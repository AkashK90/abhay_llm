"""
pipeline.py
Orchestrates the full ingestion flow for a single document.
Called by the Celery task; can also be called directly for testing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ingestion.parser import parse_document, ParsedDocument
from ingestion.chunker import chunk_document, TextChunk

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    document_id: str
    page_count: int
    chunk_count: int
    chunks: list[TextChunk]
    parsed: ParsedDocument


def run_ingestion_pipeline(
    document_id: str,
    file_path: str,
    mime_type: str,
    chunk_size: int = 800,
    chunk_overlap: int = 80,
) -> IngestionResult:
    """
    1. Parse file → text + page metadata
    2. Chunk text
    3. Return IngestionResult (embedding + storing is done by caller/task)
    """
    logger.info("[Pipeline] Starting ingestion for document_id=%s", document_id)

    # Step 1 — Parse
    parsed = parse_document(file_path, mime_type)
    logger.info(
        "[Pipeline] Parsed %d pages from %s", parsed.page_count, file_path
    )

    # Step 2 — Chunk
    chunks = chunk_document(parsed, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    logger.info("[Pipeline] Produced %d chunks", len(chunks))

    return IngestionResult(
        document_id=document_id,
        page_count=parsed.page_count,
        chunk_count=len(chunks),
        chunks=chunks,
        parsed=parsed,
    )
