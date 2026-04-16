# RAG Pipeline - Root Cause Analysis

## Issues Identified

### 1. **CRITICAL: Embedding Model Mismatch**
- **Problem**: Some documents fail because `models/text-embedding-004` is not available in Gemini API
- **Evidence**: Failed documents have error: `404 models/text-embedding-004 is not found for API version v1beta`
- **Current behavior**: Worker retries and switches to `models/gemini-embedding-001` (works)
- **Solution**: Update `.env` to use a supported model that works for both ingestion and query

### 2. **Query Returns 0 Chunks**
- **Root cause**: The query uses placeholder `"string"` in `document_ids` instead of actual UUIDs
- **Why it fails**: ChromaDB metadata filter `{"document_id": {"$eq": "string"}}` finds nothing
- **Solution**: 
  a) Pass empty list `[]` to search all documents, OR
  b) Pass actual document IDs from upload response

### 3. **Database Persistence Issue** ( EXPLAINED)
- **Why documents seem to need re-uploading**: They're not persisting in the query results
- **Actual cause**: Same query issue - if you pass wrong document_ids, nothing is found even though docs exist

### 4. **Single Document Upload Endpoint**
- **Issue**: Need to remove `/api/v1/documents/upload` (single document)
- **Keep**: `/api/v1/documents/upload-multiple` (batch uploads)

## Verified Facts
✅ Documents ARE ingesting successfully (DB shows completed status)
✅ Chunks ARE being stored in database (7 documents with 37 total chunks)
✅ ChromaDB IS receiving vectors (worker logs confirm upsert)
✅ Celery worker IS processing tasks (logs show completion)

## Why Query Fails
The query endpoint receives `document_ids: ["string"]` which:
1. Creates invalid ChromaDB filter: `{"document_id": {"$eq": "string"}}`
2. ChromaDB returns 0 results
3. RAG system returns default "no content found" message

## Solutions Required
1. Update embedding model in config
2. Fix query endpoint to handle empty document_ids properly
3. Remove single document upload endpoint
4. Test query with actual document IDs
