"""
test_query_endpoint.py
Integration tests for POST /api/v1/query
"""
import io
import pytest


class TestQueryEndpoint:
    def test_query_returns_200(self, client):
        response = client.post(
            "/api/v1/query",
            json={"question": "What is machine learning?"},
        )
        assert response.status_code == 200

    def test_query_response_has_required_fields(self, client):
        response = client.post(
            "/api/v1/query",
            json={"question": "Explain deep learning."},
        )
        data = response.json()
        assert "question" in data
        assert "answer" in data
        assert "sources" in data
        assert "chunks_retrieved" in data
        assert "model_used" in data

    def test_query_echoes_question(self, client):
        question = "What are transformer models?"
        response = client.post("/api/v1/query", json={"question": question})
        assert response.json()["question"] == question

    def test_query_answer_is_string(self, client):
        response = client.post(
            "/api/v1/query",
            json={"question": "What is a neural network?"},
        )
        assert isinstance(response.json()["answer"], str)
        assert len(response.json()["answer"]) > 0

    def test_query_sources_is_list(self, client):
        response = client.post(
            "/api/v1/query",
            json={"question": "What is backpropagation?"},
        )
        assert isinstance(response.json()["sources"], list)

    def test_source_reference_fields(self, client):
        response = client.post(
            "/api/v1/query",
            json={"question": "Explain gradient descent."},
        )
        sources = response.json()["sources"]
        if sources:
            source = sources[0]
            assert "document_id" in source
            assert "document_name" in source
            assert "relevance_score" in source
            assert "text_preview" in source
            assert 0.0 <= source["relevance_score"] <= 1.0

    def test_query_with_document_id_filter(self, client):
        response = client.post(
            "/api/v1/query",
            json={
                "question": "What is AI?",
                "document_ids": ["some-doc-uuid"],
            },
        )
        assert response.status_code == 200

    def test_query_with_custom_top_k(self, client):
        response = client.post(
            "/api/v1/query",
            json={"question": "What is NLP?", "top_k": 3},
        )
        assert response.status_code == 200

    def test_empty_question_returns_422(self, client):
        response = client.post(
            "/api/v1/query",
            json={"question": "  "},
        )
        assert response.status_code == 422

    def test_question_too_short_returns_422(self, client):
        response = client.post(
            "/api/v1/query",
            json={"question": "hi"},
        )
        assert response.status_code == 422

    def test_missing_question_field_returns_422(self, client):
        response = client.post("/api/v1/query", json={})
        assert response.status_code == 422

    def test_query_after_upload(self, client):
        """End-to-end: upload doc then query (task is mocked/sync in tests)."""
        client.post(
            "/api/v1/documents/upload",
            files={"file": ("e2e.txt", io.BytesIO(b"End to end test content about AI."), "text/plain")},
        )
        response = client.post(
            "/api/v1/query",
            json={"question": "What does this document say about AI?"},
        )
        assert response.status_code == 200
        assert response.json()["answer"]


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
