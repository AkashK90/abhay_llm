"""
embedding_service.py
Wraps the Gemini text-embedding-004 model.
Supports single and batched embedding with simple retry logic.
"""
from __future__ import annotations

import logging
import time
from typing import Sequence

import google.generativeai as genai

from app.config import get_settings

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100          # Gemini batch limit
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0         # seconds


class EmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self._model_candidates = self._build_model_candidates(settings.gemini_embed_model)
        self._active_model = self._model_candidates[0]
        self._dimension = settings.gemini_embed_dimension
        logger.info("Embedding model candidates: %s", self._model_candidates)

    def embed_text(self, text: str) -> list[float]:
        """Embed a single string. Used for query-time embedding."""
        return self._embed_with_retry([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Embed multiple texts, splitting into batches automatically.
        Returns embeddings in the same order as input.
        """
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            embeddings = self._embed_with_retry(batch)
            all_embeddings.extend(embeddings)
            logger.debug(
                "Embedded batch %d-%d / %d",
                i + 1,
                min(i + _BATCH_SIZE, len(texts)),
                len(texts),
            )
        return all_embeddings

    def _embed_with_retry(self, texts: Sequence[str]) -> list[list[float]]:
        model_candidates = [self._active_model] + [
            m for m in self._model_candidates if m != self._active_model
        ]

        for attempt in range(1, _MAX_RETRIES + 1):
            last_error: Exception | None = None
            for model in model_candidates:
                try:
                    result = genai.embed_content(
                        model=model,
                        content=list(texts),
                        task_type="retrieval_document",
                    )
                    embeddings = result.get("embedding") or result.get("embeddings")
                    if embeddings is None:
                        raise ValueError(f"Unexpected Gemini embed response: {result}")

                    if isinstance(embeddings[0], float):
                        embeddings = [embeddings]

                    if model != self._active_model:
                        logger.warning(
                            "Switched embedding model from '%s' to '%s'",
                            self._active_model,
                            model,
                        )
                        self._active_model = model

                    return [list(e) for e in embeddings]
                except Exception as exc:
                    last_error = exc
                    error_text = str(exc)
                    is_model_not_supported = (
                        "is not found" in error_text
                        or "not supported for embedContent" in error_text
                        or "404" in error_text
                        or "Invalid model name" in error_text
                    )
                    logger.warning(
                        "Embedding model '%s' failed on attempt %d/%d: %s",
                        model,
                        attempt,
                        _MAX_RETRIES,
                        exc,
                    )
                    if not is_model_not_supported:
                        break

            if attempt == _MAX_RETRIES and last_error is not None:
                raise last_error
            time.sleep(_RETRY_DELAY * attempt)

        raise RuntimeError("Embedding failed after all retries")  # unreachable

    @staticmethod
    def _build_model_candidates(configured_model: str) -> list[str]:
        configured = configured_model.strip()
        candidates: list[str] = []

        def add(value: str) -> None:
            if value and value not in candidates:
                candidates.append(value)

        add(configured)
        if configured.startswith("models/"):
            add(configured.replace("models/", "", 1))
        else:
            add(f"models/{configured}")

        for fallback in (
            "text-embedding-004",
            "models/text-embedding-004",
            "gemini-embedding-001",
            "models/gemini-embedding-001",
        ):
            add(fallback)

        return candidates


# Module-level singleton — imported by services and tasks
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
