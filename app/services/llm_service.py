"""
llm_service.py
Wraps Gemini 2.5 Flash for RAG-style answer generation.
"""
from __future__ import annotations

import logging
import time

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from app.config import get_settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAY = 2.0

_RAG_SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions based on the provided document context.

Instructions:
- Answer ONLY using information from the provided context chunks.
- If the context does not contain enough information to answer, say so clearly.
- Be concise and accurate.
- When referencing specific information, mention the source (e.g., "According to the document...").
- Do not hallucinate facts or information not present in the context.
"""


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(
            model_name=settings.gemini_llm_model,
            system_instruction=_RAG_SYSTEM_PROMPT,
            generation_config=GenerationConfig(
                temperature=0.2,
                top_p=0.9,
                max_output_tokens=2048,
            ),
        )

    def generate_answer(
        self,
        question: str,
        context_chunks: list[str],
    ) -> str:
        """
        Build a RAG prompt and generate an answer from Gemini.
        context_chunks: ordered list of retrieved text chunks (most relevant first).
        """
        context_block = "\n\n---\n\n".join(
            f"[Chunk {i + 1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
        )
        prompt = (
            f"Context from uploaded documents:\n\n{context_block}\n\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )

        return self._generate_with_retry(prompt)

    def _generate_with_retry(self, prompt: str) -> str:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._model.generate_content(prompt)
                return response.text
            except Exception as exc:
                logger.warning(
                    "LLM generation attempt %d/%d failed: %s", attempt, _MAX_RETRIES, exc
                )
                if attempt == _MAX_RETRIES:
                    raise
                time.sleep(_RETRY_DELAY * attempt)
        raise RuntimeError("LLM generation failed after all retries")


_llm_service: LLMService | None = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
