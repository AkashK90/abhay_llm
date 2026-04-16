"""
query.py
REST endpoint for RAG question answering.

POST /api/v1/query
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.query import QueryRequest, QueryResponse, SourceReferenceSchema
from app.services.query_service import answer_question

router = APIRouter(prefix="/query", tags=["Query"])


@router.post(
    "",
    response_model=QueryResponse,
    summary="Ask a question against uploaded documents",
)
def query_documents(
    request: QueryRequest,
    db: Session = Depends(get_db),
):
    """
    Submit a natural language question. The system:

    1. Embeds the question using Gemini text-embedding-004
    2. Retrieves the most relevant document chunks from ChromaDB
    3. Passes chunks + question to Gemini 2.5 Flash
    4. Returns the generated answer with source citations

    Optionally filter retrieval to specific `document_ids`.
    All referenced documents must have status = `completed`.
    """
    try:
        result = answer_question(
            question=request.question,
            db=db,
            document_ids=request.document_ids,
            top_k=request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {exc}",
        )

    return QueryResponse(
        question=result.question,
        answer=result.answer,
        sources=[
            SourceReferenceSchema(
                document_id=s.document_id,
                document_name=s.document_name,
                chunk_index=s.chunk_index,
                page_number=s.page_number,
                relevance_score=s.relevance_score,
                text_preview=s.text_preview,
            )
            for s in result.sources
        ],
        chunks_retrieved=result.chunks_retrieved,
        model_used=result.model_used,
    )
