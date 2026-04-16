"""
test_query_service.py
Unit tests for app/services/query_service.py
All external calls (Gemini, ChromaDB) are mocked.
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock

from app.services.query_service import answer_question, _fetch_document_names, QueryResult
from app.services.vector_store import RetrievedChunk


def _make_chunk(doc_id: str = "doc-1", score: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        chroma_id=str(uuid.uuid4()),
        document_id=doc_id,
        chunk_index=0,
        page_number=1,
        text="Context text about the topic being asked.",
        distance=1.0 - score,
        score=score,
    )


class TestAnswerQuestion:
    def test_returns_query_result(self, db, mock_embedding_service, mock_llm_service, mock_vector_store):
        with (
            patch("app.services.query_service.get_embedding_service", return_value=mock_embedding_service),
            patch("app.services.query_service.get_vector_store", return_value=mock_vector_store),
            patch("app.services.query_service.get_llm_service", return_value=mock_llm_service),
        ):
            result = answer_question("What is machine learning?", db=db)

        assert isinstance(result, QueryResult)
        assert result.question == "What is machine learning?"
        assert result.answer == "This is a mocked answer from the LLM."
        assert result.chunks_retrieved >= 1

    def test_embedding_called_once(self, db, mock_embedding_service, mock_llm_service, mock_vector_store):
        with (
            patch("app.services.query_service.get_embedding_service", return_value=mock_embedding_service),
            patch("app.services.query_service.get_vector_store", return_value=mock_vector_store),
            patch("app.services.query_service.get_llm_service", return_value=mock_llm_service),
        ):
            answer_question("What is deep learning?", db=db)

        mock_embedding_service.embed_text.assert_called_once_with("What is deep learning?")

    def test_empty_retrieval_returns_no_context_answer(self, db, mock_embedding_service, mock_llm_service, mock_vector_store):
        mock_vector_store.similarity_search.return_value = []

        with (
            patch("app.services.query_service.get_embedding_service", return_value=mock_embedding_service),
            patch("app.services.query_service.get_vector_store", return_value=mock_vector_store),
            patch("app.services.query_service.get_llm_service", return_value=mock_llm_service),
        ):
            result = answer_question("What is quantum computing?", db=db)

        assert result.chunks_retrieved == 0
        assert result.sources == []
        assert "could not find" in result.answer.lower()

    def test_document_id_filter_passed_to_vector_store(self, db, mock_embedding_service, mock_llm_service, mock_vector_store):
        doc_ids = ["doc-abc", "doc-xyz"]

        with (
            patch("app.services.query_service.get_embedding_service", return_value=mock_embedding_service),
            patch("app.services.query_service.get_vector_store", return_value=mock_vector_store),
            patch("app.services.query_service.get_llm_service", return_value=mock_llm_service),
        ):
            answer_question("Some question", db=db, document_ids=doc_ids)

        call_kwargs = mock_vector_store.similarity_search.call_args
        assert call_kwargs.kwargs.get("document_ids") == doc_ids

    def test_empty_question_raises_value_error(self, db, mock_embedding_service, mock_llm_service, mock_vector_store):
        with pytest.raises(ValueError, match="empty"):
            answer_question("   ", db=db)

    def test_sources_have_correct_structure(self, db, mock_embedding_service, mock_llm_service, mock_vector_store):
        with (
            patch("app.services.query_service.get_embedding_service", return_value=mock_embedding_service),
            patch("app.services.query_service.get_vector_store", return_value=mock_vector_store),
            patch("app.services.query_service.get_llm_service", return_value=mock_llm_service),
        ):
            result = answer_question("What is AI?", db=db)

        for source in result.sources:
            assert hasattr(source, "document_id")
            assert hasattr(source, "relevance_score")
            assert 0.0 <= source.relevance_score <= 1.0
            assert len(source.text_preview) <= 300


class TestFetchDocumentNames:
    def test_returns_empty_dict_for_empty_ids(self, db):
        result = _fetch_document_names(db, [])
        assert result == {}

    def test_returns_mapping_for_known_docs(self, db):
        from app.db.models.document import Document
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        doc = Document(
            id="fetch-test-doc",
            filename="stored.txt",
            original_filename="my_report.txt",
            file_path="/tmp/stored.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        db.add(doc)
        db.commit()

        result = _fetch_document_names(db, ["fetch-test-doc"])
        assert result == {"fetch-test-doc": "my_report.txt"}
