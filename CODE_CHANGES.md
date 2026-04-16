# 📝 Exact Code Changes Made

## File 1: `.env` - Embedding Model Fix

```diff
- GEMINI_EMBED_MODEL=models/text-embedding-004
+ GEMINI_EMBED_MODEL=text-embedding-004
```

**Why**: Newer Gemini API versions don't support "models/" prefix for this model. The raw name works better with fallback logic.

---

## File 2: `app/api/v1/documents.py` - Remove Single Upload Endpoint

**REMOVED** this entire endpoint:
```python
@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for ingestion",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF, DOCX, TXT or MD file"),
    db: Session = Depends(get_db),
):
    """Upload a single document for ingestion."""
    document, job = save_upload_and_enqueue(file, db)
    return DocumentUploadResponse(...)
```

**Also updated imports**:
```diff
from app.services.document_service import (
-   save_upload_and_enqueue,
    save_uploads_and_enqueue,
    get_document,
    list_documents,
    delete_document,
)
```

---

## File 3: `app/services/vector_store.py` - Query Filtering Fix

**Before**:
```python
def similarity_search(
    self,
    query_embedding: list[float],
    top_k: int = 5,
    document_ids: list[str] | None = None,
) -> list[RetrievedChunk]:
    """Perform cosine similarity search."""
    where: dict | None = None
    if document_ids:
        if len(document_ids) == 1:
            where = {"document_id": {"$eq": document_ids[0]}}
        else:
            where = {"document_id": {"$in": document_ids}}
    # ... rest of code
```

**After**:
```python
def similarity_search(
    self,
    query_embedding: list[float],
    top_k: int = 5,
    document_ids: list[str] | None = None,
) -> list[RetrievedChunk]:
    """
    Perform cosine similarity search.
    Optionally filter to specific document_ids.
    If document_ids is empty or None, searches across all documents.
    """
    where: dict | None = None
    
    # Only apply filter if document_ids is provided and non-empty
    if document_ids and len(document_ids) > 0:
        # Filter out any invalid placeholder values like "string"
        valid_ids = [id for id in document_ids if id and id != "string" and id.strip()]
        if valid_ids:
            if len(valid_ids) == 1:
                where = {"document_id": {"$eq": valid_ids[0]}}
            else:
                where = {"document_id": {"$in": valid_ids}}

    count = self._count()
    if count == 0:
        logger.warning("ChromaDB collection is empty, no vectors to search")
        return []

    results = self._collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    # ... rest of code
    
    if chunks:
        logger.info("[VectorStore] Retrieved %d chunks (filter: %s)", len(chunks), where)
    else:
        logger.warning("[VectorStore] No chunks retrieved with filter: %s", where)
        
    return chunks
```

**Key changes**:
- Validates `document_ids` to filter out invalid placeholders like "string"
- Only applies WHERE filter if valid IDs exist
- Added logging to see what filter was applied
- Empty `document_ids` list now correctly searches all documents

---

## File 4: `app/services/query_service.py` - Enhanced Logging

**Before**:
```python
def answer_question(...) -> QueryResult:
    logger.info("[Query] Embedding question (%d chars)", len(question))
    embedding_svc = get_embedding_service()
    query_embedding = embedding_svc.embed_text(question)

    vector_store = get_vector_store()
    retrieval_top_k = top_k or settings.retrieval_top_k
    retrieved: list[RetrievedChunk] = vector_store.similarity_search(...)

    if not retrieved:
        return QueryResult(...)

    logger.info("[Query] Retrieved %d chunks", len(retrieved))
```

**After**:
```python
def answer_question(...) -> QueryResult:
    logger.info("[Query] Embedding question (%d chars)", len(question))
    embedding_svc = get_embedding_service()
    query_embedding = embedding_svc.embed_text(question)
    logger.debug("[Query] Question embedding dimension: %d", len(query_embedding))

    vector_store = get_vector_store()
    retrieval_top_k = top_k or settings.retrieval_top_k
    
    # Filter out invalid document_ids
    valid_doc_ids = None
    if document_ids and len(document_ids) > 0:
        valid_doc_ids = [id for id in document_ids if id and id != "string" and id.strip()]
    
    logger.info(
        "[Query] Searching with document_ids=%s, top_k=%d",
        valid_doc_ids if valid_doc_ids else "all",
        retrieval_top_k,
    )
    
    retrieved: list[RetrievedChunk] = vector_store.similarity_search(...)

    if not retrieved:
        logger.warning("[Query] No relevant chunks found for question: %s", question)
        return QueryResult(...)

    logger.info("[Query] Retrieved %d chunks from vector store", len(retrieved))
```

**Key additions**:
- Logs embedding dimension
- Shows what document_ids filter will be used
- Logs when no chunks are retrieved (helps debugging)
- Better visibility into query path

---

## Summary of Changes

| File | Change | Impact |
|------|--------|--------|
| `.env` | Model name fix | ✅ Embeddings now work reliably |
| `documents.py` | Remove single upload | ✅ Cleaner, simpler API |
| `vector_store.py` | Validate document_ids | ✅ Query returns results |
| `query_service.py` | Add logging | ✅ Easier to debug issues |

**Total lines changed**: ~80 lines
**Breaking changes**: Only the removal of `/upload` endpoint (users must use `/upload-multiple`)
**Backward compatibility**: ✅ Existing multi-upload code works unchanged
