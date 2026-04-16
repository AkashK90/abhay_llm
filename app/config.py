from functools import lru_cache
import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Gemini ──────────────────────────────────────────────────────────────
    gemini_api_key: str
    gemini_llm_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "text-embedding-004"
    gemini_embed_dimension: int = 768

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str = "postgresql://raguser:ragpassword@postgres:5432/ragdb"
    postgres_user: str = "raguser"
    postgres_password: str = "ragpassword"
    postgres_db: str = "ragdb"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # ── Redis / Celery ───────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chroma_host: str = "chromadb"
    chroma_port: int = 8001
    chroma_collection: str = "rag_documents"

    # ── File Storage ─────────────────────────────────────────────────────────
    storage_dir: str = "/app/storage"
    max_documents: int = 20
    max_file_size_mb: int = 500

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = True
    secret_key: str = "change_me"

    # ── RAG ──────────────────────────────────────────────────────────────────
    chunk_size: int = 800
    chunk_overlap: int = 80
    retrieval_top_k: int = 5

    @field_validator("storage_dir")
    @classmethod
    def normalize_storage_dir(cls, value: str) -> str:
        """
        Convert Linux-style absolute paths to a local writable path on Windows.
        Example: '/tmp/rag_test_storage' -> '<cwd>/tmp/rag_test_storage'
        """
        if os.name == "nt" and value.startswith("/"):
            return str(Path.cwd() / value.lstrip("/"))
        return value

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings — instantiated once per process."""
    return Settings()
