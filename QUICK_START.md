# 🚀 RAG Pipeline - Quick Start Guide

## Status: ✅ FULLY OPERATIONAL

All issues have been fixed. The system is ready to use.

---

## 📥 Step 1: Upload Documents

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload-multiple \
  -H "Content-Type: multipart/form-data" \
  -F "files=@your_document1.pdf" \
  -F "files=@your_document2.txt"
```

**Expected Response**:
```json
{
  "total_uploaded": 2,
  "uploads": [
    {
      "document_id": "abc-123-def-456",
      "job_id": "job-xyz-789",
      "original_filename": "your_document1.pdf",
      "status": "pending"
    }
  ]
}
```

**Save the `document_id` values** - you'll use these later if needed.

---

## ⏳ Step 2: Wait for Processing

Documents are processed by Celery workers asynchronously.

**Typical processing times**:
- Small text files: 2-5 seconds
- PDF with multiple pages: 10-20 seconds
- Large batch: up to 1 minute

**Track progress** (optional):
```bash
# Check document status
curl http://localhost:8000/api/v1/documents | jq '.documents[] | {id, status, chunk_count}'

# Output should show: status: "completed"
```

---

## ❓ Step 3: Ask Questions

**DO THIS** (empty document_ids):
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main skills?",
    "document_ids": [],
    "top_k": 5
  }'
```

**OR THIS** (specific documents):
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main skills?",
    "document_ids": ["abc-123-def-456", "xyz-789-etc-012"],
    "top_k": 5
  }'
```

**Response Example**:
```json
{
  "question": "What are the main skills?",
  "answer": "Based on the documents, the main skills include...",
  "sources": [
    {
      "document_id": "abc-123-def-456",
      "document_name": "Akash_cv_s.pdf",
      "chunk_index": 0,
      "relevance_score": 0.83,
      "text_preview": "Skills: Python, Machine Learning..."
    }
  ],
  "chunks_retrieved": 3,
  "model_used": "gemini-2.5-flash"
}
```

---

## 🎯 Common Use Cases

### Search Everything
```json
{
  "question": "Tell me everything about the project",
  "document_ids": [],
  "top_k": 10
}
```

### Search Specific Document Only
```json
{
  "question": "What's in the budget report?",
  "document_ids": ["my-budget-doc-id"],
  "top_k": 5
}
```

### Search Multiple Specific Documents
```json
{
  "question": "Compare these two reports",
  "document_ids": ["doc-id-1", "doc-id-2"],
  "top_k": 8
}
```

---

## 🔄 Delete and Re-upload

To start fresh with new documents:

```bash
# Delete a document
curl -X DELETE http://localhost:8000/api/v1/documents/{document_id}

# Upload new documents
curl -X POST http://localhost:8000/api/v1/documents/upload-multiple \
  -F "files=@new_doc.pdf"
```

---

## ❓ Troubleshooting

### "No relevant content found"
1. Documents may still be processing - wait a minute
2. Check status: `curl http://localhost:8000/api/v1/documents`
3. Try searching with empty `document_ids: []`
4. Check worker logs: `docker compose logs worker`

### Upload fails with 422 error
1. File format not supported - use PDF, DOCX, TXT, or MD
2. File too large - max 500MB (configurable)
3. Too many documents - max 20 (configurable)

### Slow responses
1. Gemini API is rate-limited
2. Large documents take longer to embed
3. Wait between batch uploads (10+ sec)

### Container issues
```bash
# Restart all containers
docker compose restart

# Force rebuild
docker compose down -v
docker compose up -d --build

# View logs
docker compose logs -f worker
docker compose logs -f api
```

---

## 📊 Monitoring

### Check System Health
```bash
curl http://localhost:8000/health
```

### View All Documents
```bash
curl http://localhost:8000/api/v1/documents | jq
```

### Monitor Celery Tasks (Flower UI)
Open browser: `http://localhost:5555`

### Database Status
```bash
docker compose exec -T postgres psql -U raguser -d ragdb -c "\dt"
```

---

## 🐳 Docker Commands

```bash
# Start everything
docker compose up -d

# Stop everything
docker compose down

# View logs
docker compose logs worker -f
docker compose logs api -f
docker compose logs -f

# Rebuild after code changes
docker compose up -d --build

# Clean everything (WARNING: deletes data)
docker compose down -v
```

---

## 📋 API Reference

### Documents
- `POST /api/v1/documents/upload-multiple` - Upload files ⭐
- `GET /api/v1/documents` - List all documents
- `GET /api/v1/documents/{id}` - Get document details
- `DELETE /api/v1/documents/{id}` - Delete document

### Query (RAG)
- `POST /api/v1/query` - Ask questions ⭐

### Jobs
- `GET /api/v1/jobs/{job_id}` - Track ingestion

### Health
- `GET /health` - Service health

---

## ⚙️ Configuration

Edit `.env` to customize:

```env
# Gemini API
GEMINI_API_KEY=your-key-here
GEMINI_LLM_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=text-embedding-004

# Document processing
CHUNK_SIZE=800          # Characters per chunk
CHUNK_OVERLAP=80        # Character overlap between chunks
RETRIEVAL_TOP_K=5       # Default number of chunks to retrieve

# Storage
STORAGE_DIR=/app/storage
MAX_DOCUMENTS=20        # Max documents allowed
MAX_FILE_SIZE_MB=500    # Max file size

# ChromaDB
CHROMA_HOST=chromadb
CHROMA_PORT=8000
```

Then rebuild: `docker compose up -d --build`

---

## 💡 Pro Tips

1. **Use empty document_ids** to search everything
2. **Increase top_k** for broader search (up to 20)
3. **Use specific document_ids** for targeted queries
4. **Check relevance_score** in sources (higher = better)
5. **Monitor worker logs** during bulk uploads
6. **Keep chunk_size between 500-1000** characters

---

## 📞 Support

**Check logs**:
- Worker errors: `docker compose logs worker`
- API errors: `docker compose logs api`
- Database issues: `docker compose logs postgres`

**Common issues**:
- See SOLUTION_SUMMARY.md
- See DEBUG_ANALYSIS.md
- See CODE_CHANGES.md

---

**Last updated**: April 15, 2026
**Status**: ✅ Production Ready
