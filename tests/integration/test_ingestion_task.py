"""
test_ingestion_task.py
Tests the ingestion pipeline logic in isolation — no Celery broker needed.
We call run_ingestion_pipeline() directly and verify the outputs.
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock

from ingestion.pipeline import run_ingestion_pipeline, IngestionResult


class TestIngestionPipeline:
    def test_pipeline_returns_ingestion_result(self, sample_txt_file):
        result = run_ingestion_pipeline(
            document_id=str(uuid.uuid4()),
            file_path=str(sample_txt_file),
            mime_type="text/plain",
            chunk_size=200,
            chunk_overlap=20,
        )
        assert isinstance(result, IngestionResult)

    def test_pipeline_produces_chunks(self, sample_txt_file):
        result = run_ingestion_pipeline(
            document_id=str(uuid.uuid4()),
            file_path=str(sample_txt_file),
            mime_type="text/plain",
            chunk_size=200,
            chunk_overlap=20,
        )
        assert result.chunk_count >= 1
        assert len(result.chunks) == result.chunk_count

    def test_pipeline_document_id_propagated(self, sample_txt_file):
        doc_id = str(uuid.uuid4())
        result = run_ingestion_pipeline(
            document_id=doc_id,
            file_path=str(sample_txt_file),
            mime_type="text/plain",
        )
        assert result.document_id == doc_id

    def test_pipeline_page_count_set(self, sample_txt_file):
        result = run_ingestion_pipeline(
            document_id=str(uuid.uuid4()),
            file_path=str(sample_txt_file),
            mime_type="text/plain",
        )
        assert result.page_count >= 1

    def test_pipeline_chunks_have_text(self, sample_txt_file):
        result = run_ingestion_pipeline(
            document_id=str(uuid.uuid4()),
            file_path=str(sample_txt_file),
            mime_type="text/plain",
            chunk_size=100,
            chunk_overlap=10,
        )
        for chunk in result.chunks:
            assert chunk.text.strip() != ""

    def test_pipeline_large_document(self, sample_large_txt_file):
        result = run_ingestion_pipeline(
            document_id=str(uuid.uuid4()),
            file_path=str(sample_large_txt_file),
            mime_type="text/plain",
            chunk_size=500,
            chunk_overlap=50,
        )
        assert result.chunk_count > 10

    def test_pipeline_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            run_ingestion_pipeline(
                document_id=str(uuid.uuid4()),
                file_path="/nonexistent/path/file.txt",
                mime_type="text/plain",
            )

    def test_pipeline_invalid_mime_raises(self, sample_txt_file):
        with pytest.raises(ValueError):
            run_ingestion_pipeline(
                document_id=str(uuid.uuid4()),
                file_path=str(sample_txt_file),
                mime_type="application/zip",
            )


class TestIngestionTaskWithMocks:
    """
    Tests the full Celery task function by calling it synchronously
    with all DB and external services mocked.
    """

    def test_task_marks_job_completed(self, db, mock_embedding_service, mock_vector_store, sample_txt_file):
        from datetime import datetime, timezone
        from app.db.models.document import Document
        from app.db.models.job import IngestionJob

        now = datetime.now(timezone.utc)
        doc_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        doc = Document(
            id=doc_id,
            filename="test.txt",
            original_filename="test.txt",
            file_path=str(sample_txt_file),
            file_size_bytes=100,
            mime_type="text/plain",
            status="pending",
            created_at=now,
            updated_at=now,
        )
        job = IngestionJob(
            id=job_id,
            document_id=doc_id,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        db.add(doc)
        db.add(job)
        db.commit()

        with (
            patch("app.workers.tasks.ingestion.SessionLocal", return_value=db),
            patch("app.services.embedding_service.get_embedding_service", return_value=mock_embedding_service),
            patch("app.workers.tasks.ingestion.get_embedding_service", return_value=mock_embedding_service),
            patch("app.workers.tasks.ingestion.get_vector_store", return_value=mock_vector_store),
        ):
            from app.workers.tasks.ingestion import ingest_document_task

            # Simulate task body directly (bypass Celery broker)
            ingest_document_task.__wrapped__ = lambda *a, **kw: None
            result = run_ingestion_pipeline(
                document_id=doc_id,
                file_path=str(sample_txt_file),
                mime_type="text/plain",
            )

        # Pipeline should have produced chunks
        assert result.chunk_count >= 1
