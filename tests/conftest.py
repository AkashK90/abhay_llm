"""
conftest.py
Shared fixtures for the entire test suite.

Key design decisions:
  - Uses SQLite in-memory for DB tests (no Postgres needed to run unit tests).
  - Mocks EmbeddingService and LLMService so no Gemini API key is required.
  - Provides a pre-built FastAPI TestClient wired to the test DB.
"""
from __future__ import annotations

import os
import uuid
import pytest
from typing import Generator
from unittest.mock import MagicMock, patch

# Point to SQLite before any app import so config picks it up
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("CHROMA_HOST", "localhost")
os.environ.setdefault("CHROMA_PORT", "8001")
os.environ.setdefault("STORAGE_DIR", "/tmp/rag_test_storage")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

# ── Database ──────────────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite:///./test_rag.db"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    # Enable FK enforcement in SQLite
    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture(scope="function")
def db(engine) -> Generator[Session, None, None]:
    """Provide a transactional DB session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection)
    session = TestSession()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ── Mocked external services ──────────────────────────────────────────────────

@pytest.fixture
def mock_embedding_service():
    """Returns a fixed 4-dim embedding vector (no real Gemini calls)."""
    mock = MagicMock()
    mock.embed_text.return_value = [0.1, 0.2, 0.3, 0.4]
    mock.embed_batch.side_effect = lambda texts: [[0.1, 0.2, 0.3, 0.4]] * len(texts)
    return mock


@pytest.fixture
def mock_llm_service():
    mock = MagicMock()
    mock.generate_answer.return_value = "This is a mocked answer from the LLM."
    return mock


@pytest.fixture
def mock_vector_store():
    from app.services.vector_store import RetrievedChunk

    mock = MagicMock()
    mock.similarity_search.return_value = [
        RetrievedChunk(
            chroma_id=str(uuid.uuid4()),
            document_id="test-doc-id",
            chunk_index=0,
            page_number=1,
            text="This is relevant context about the topic.",
            distance=0.1,
            score=0.9,
        )
    ]
    mock.upsert_chunks.return_value = None
    mock.delete_document.return_value = 3
    return mock


# ── FastAPI TestClient ────────────────────────────────────────────────────────

@pytest.fixture
def client(db, mock_embedding_service, mock_llm_service, mock_vector_store):
    """
    Full TestClient with:
     - SQLite test DB injected via dependency override
     - All external services mocked
     - Celery tasks executed eagerly (CELERY_TASK_ALWAYS_EAGER)
    """
    app = create_app()

    # Override DB dependency
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("app.services.embedding_service.get_embedding_service", return_value=mock_embedding_service),
        patch("app.services.llm_service.get_llm_service", return_value=mock_llm_service),
        patch("app.services.vector_store.get_vector_store", return_value=mock_vector_store),
        patch("app.services.document_service.get_vector_store", return_value=mock_vector_store),
        # Run Celery tasks synchronously in tests
        patch("app.workers.tasks.ingestion.ingest_document_task.delay") as mock_delay,
    ):
        mock_delay.return_value = MagicMock(id="celery-task-test-id")
        with TestClient(app) as c:
            yield c


# ── Sample file fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_txt_file(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text(
        "This is a sample document about machine learning.\n\n"
        "Machine learning is a subset of artificial intelligence.\n\n"
        "It allows computers to learn from data without being explicitly programmed.\n\n"
        "Deep learning uses neural networks with many layers.",
        encoding="utf-8",
    )
    return f


@pytest.fixture
def sample_large_txt_file(tmp_path):
    """A file large enough to produce multiple chunks."""
    content = "\n\n".join(
        f"Section {i}: " + ("lorem ipsum dolor sit amet consectetur. " * 30)
        for i in range(50)
    )
    f = tmp_path / "large_sample.txt"
    f.write_text(content, encoding="utf-8")
    return f
