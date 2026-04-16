"""
test_upload_endpoint.py
Integration tests for POST /api/v1/documents/upload and related endpoints.
Uses the full FastAPI TestClient with mocked Celery and external services.
"""
import io
import pytest


class TestUploadEndpoint:
    def test_upload_txt_returns_202(self, client):
        content = b"This is a test document about artificial intelligence and RAG pipelines."
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test_doc.txt", io.BytesIO(content), "text/plain")},
        )
        assert response.status_code == 202, response.text

    def test_upload_response_has_required_fields(self, client):
        content = b"RAG pipeline test document content."
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("doc.txt", io.BytesIO(content), "text/plain")},
        )
        data = response.json()
        assert "document_id" in data
        assert "job_id" in data
        assert "status" in data
        assert data["status"] == "pending"

    def test_upload_sets_correct_filename(self, client):
        content = b"Some document content."
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("my_report.txt", io.BytesIO(content), "text/plain")},
        )
        data = response.json()
        assert data["original_filename"] == "my_report.txt"

    def test_upload_unsupported_extension_returns_422(self, client):
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("bad.exe", io.BytesIO(b"data"), "application/octet-stream")},
        )
        assert response.status_code == 422

    def test_upload_no_file_returns_422(self, client):
        response = client.post("/api/v1/documents/upload")
        assert response.status_code == 422

    def test_upload_md_file_accepted(self, client):
        content = b"# Heading\n\nMarkdown content."
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("notes.md", io.BytesIO(content), "text/markdown")},
        )
        assert response.status_code == 202


class TestDocumentListEndpoint:
    def test_list_returns_200(self, client):
        response = client.get("/api/v1/documents")
        assert response.status_code == 200

    def test_list_empty_initially(self, client):
        response = client.get("/api/v1/documents")
        data = response.json()
        assert "documents" in data
        assert "total" in data

    def test_list_contains_uploaded_doc(self, client):
        # Upload first
        client.post(
            "/api/v1/documents/upload",
            files={"file": ("listed.txt", io.BytesIO(b"Content for listing test."), "text/plain")},
        )
        response = client.get("/api/v1/documents")
        data = response.json()
        assert data["total"] >= 1

    def test_list_pagination_params_accepted(self, client):
        response = client.get("/api/v1/documents?skip=0&limit=10")
        assert response.status_code == 200


class TestDocumentDetailEndpoint:
    def test_get_document_by_id(self, client):
        upload = client.post(
            "/api/v1/documents/upload",
            files={"file": ("detail_test.txt", io.BytesIO(b"Detail endpoint test."), "text/plain")},
        )
        doc_id = upload.json()["document_id"]

        response = client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc_id
        assert data["original_filename"] == "detail_test.txt"

    def test_get_nonexistent_document_returns_404(self, client):
        response = client.get("/api/v1/documents/nonexistent-id-12345")
        assert response.status_code == 404

    def test_detail_has_chunks_field(self, client):
        upload = client.post(
            "/api/v1/documents/upload",
            files={"file": ("chunks_test.txt", io.BytesIO(b"Chunk test content."), "text/plain")},
        )
        doc_id = upload.json()["document_id"]
        response = client.get(f"/api/v1/documents/{doc_id}")
        assert "chunks" in response.json()


class TestDeleteEndpoint:
    def test_delete_existing_document_returns_204(self, client):
        upload = client.post(
            "/api/v1/documents/upload",
            files={"file": ("to_delete.txt", io.BytesIO(b"Will be deleted."), "text/plain")},
        )
        doc_id = upload.json()["document_id"]

        response = client.delete(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 204

    def test_deleted_document_not_found_after(self, client):
        upload = client.post(
            "/api/v1/documents/upload",
            files={"file": ("gone.txt", io.BytesIO(b"Gone document."), "text/plain")},
        )
        doc_id = upload.json()["document_id"]
        client.delete(f"/api/v1/documents/{doc_id}")

        response = client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        response = client.delete("/api/v1/documents/does-not-exist")
        assert response.status_code == 404


class TestJobStatusEndpoint:
    def test_job_status_accessible_after_upload(self, client):
        upload = client.post(
            "/api/v1/documents/upload",
            files={"file": ("job_test.txt", io.BytesIO(b"Testing job status endpoint."), "text/plain")},
        )
        job_id = upload.json()["job_id"]

        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("pending", "processing", "completed", "failed")

    def test_job_status_nonexistent_returns_404(self, client):
        response = client.get("/api/v1/jobs/nonexistent-job-id")
        assert response.status_code == 404
