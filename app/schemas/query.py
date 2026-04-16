from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)
    document_ids: list[str] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Question cannot be empty")
        return stripped


class SourceReferenceSchema(BaseModel):
    document_id: str
    document_name: str
    chunk_index: int
    page_number: int | None = None
    relevance_score: float
    text_preview: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceReferenceSchema]
    chunks_retrieved: int
    model_used: str
