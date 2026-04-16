# RAG Pipeline - Complete Fix Summary

## Changes Made

### 1. **Fixed Embedding Model** ✅
**File**: `.env`
- **Before**: `GEMINI_EMBED_MODEL=models/text-embedding-004`
- **After**: `GEMINI_EMBED_MODEL=text-embedding-004`
- **Reason**: Newer Gemini API versions need the raw model name without "models/" prefix for fallback compatibility

### 2. **Removed Single Document Upload Endpoint** ✅
**File**: `app/api/v1/documents.py`
- **Removed**: `POST /api/v1/documents/upload` endpoint (single file)
- **Kept**: `POST /api/v1/documents/upload-multiple` endpoint (batch upload)
- **Benefit**: Simplified API, batch uploads enforce consistency

### 3. **Fixed Vector Store Query Filtering** ✅
**File**: `app/services/vector_store.py`
- **Issue**: Placeholder value `"string"` in `document_ids` was creating invalid ChromaDB filters
- **Fix**: Added validation to:
  - Filter out invalid placeholder values like "string"
  - Support empty `document_ids` list (search all documents)
  - Added detailed logging for debugging
- **Result**: Queries now work with empty document_ids or actual UUIDs

### 4. **Improved Query Service Logging** ✅
**File**: `app/services/query_service.py`
- **Added**: Better debug logging to track query flow
- **Benefit**: Clearer diagnostics for troubleshooting

---

## How to Use the Fixed API

### Upload Multiple Documents
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload-multiple" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@Akash_cv_s.pdf;type=application/pdf" \
  -F "files=@Xconnectedai.pdf;type=application/pdf"
```

**Response:**
```json
{
  "total_uploaded": 2,
  "uploads": [
    {
      "document_id": "40c4a3d2-efc9-416a-98f2-3765cc38ee46",
      "job_id": "ab3edea2-e98f-4bf3-801a-7bd96c063954",
      "original_filename": "Akash_cv_s.pdf",
      "status": "pending"
    },
    ...
  ]
}
```

### Query Documents (Correct Way)

**Option 1: Search ALL documents (RECOMMENDED)**
```json
{
  "question": "What are your skills?",
  "document_ids": [],
  "top_k": 5
}
```

**Option 2: Search SPECIFIC documents** (use actual UUIDs from upload)
```json
{
  "question": "What are your skills?",
  "document_ids": [
    "40c4a3d2-efc9-416a-98f2-3765cc38ee46",
    "da35216b-791c-4484-a13b-f354fa952bf0"
  ],
  "top_k": 5
}
```

---

## Verification Checklist

✅ All containers running (API, Worker, ChromaDB, PostgreSQL, Redis)
✅ Embedding model fixed and compatible
✅ Single upload endpoint removed
✅ Vector store filtering supports empty `document_ids`
✅ Query service has enhanced logging

---

## Troubleshooting

### If "No relevant content found":
1. **Check document status**:
   ```sql
   SELECT id, original_filename, status FROM documents LIMIT 5;
   ```
   - Status should be `completed`, not `pending` or `failed`

2. **Check chunks were created**:
   ```sql
   SELECT document_id, COUNT(*) as chunk_count FROM document_chunks GROUP BY document_id;
   ```
   - Documents should have at least 1-2 chunks

3. **Test with empty document_ids**:
   - Always use `[]` first to search across all documents
   - This ensures you're testing the retrieval, not the filter

4. **View worker logs**:
   ```bash
   docker compose logs worker --tail=100
   ```
   - Look for "Ingestion completed" success messages
   - Check for embedding errors

### If embeddings are slow:
- The Gemini API rate limits calls
- Wait 10-20 seconds between large batch uploads

---

## Testing the Complete Flow

1. **Upload documents** using the multi-upload endpoint
2. **Wait 5-10 seconds** for processing (watch worker logs)
3. **Query with empty document_ids**: `{"question": "your question", "document_ids": [], "top_k": 5}`
4. **Verify response has sources** with actual document names and chunks

---

## Root Causes (What Was Wrong)

| Issue | Cause | Impact | Fix |
|-------|-------|--------|-----|
| Query returns no results | Placeholder "string" value in document_ids | ChromaDB filter found nothing | Validate and filter document_ids |
| Some documents fail | Model name format incompatible | Only fallback models work | Use raw model name, not "models/" prefix |
| API cluttered | Single + batch endpoints | Inconsistency | Remove single, keep batch only |
| Hard to debug | Minimal logging | No visibility | Added detailed query logs |

