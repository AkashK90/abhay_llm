# RAG Project

This project is a Retrieval-Augmented Generation (RAG) API built with:
- FastAPI
- Celery + Redis
- PostgreSQL
- ChromaDB
- Gemini (LLM + embeddings)

It supports:
- Single-file upload
- Multi-file upload in one request
- Asynchronous ingestion
- Querying across all uploaded documents (or filtered document IDs)

## 1. Project Structure

```text
rag-project/
- app/
  - api/v1/              # API routes
  - core/                # logging + exception handlers
  - db/                  # SQLAlchemy models + session
  - schemas/             # Pydantic schemas
  - services/            # business logic
  - workers/             # Celery app + tasks
  - main.py              # FastAPI app
- ingestion/             # parser/chunker/pipeline
- alembic/               # DB migrations
- docker/                # dockerfiles
- tests/                 # unit + integration tests
- docker-compose.yml
- requirements.txt
- .env.example
```

## 2. Prerequisites

- Docker Desktop (must be running)
- Docker Compose v2
- Gemini API key

## 3. Step-by-Step Run Guide (Windows PowerShell)

1. Open Docker Desktop and wait until it shows Running.

2. Go to project directory:
```powershell
cd "c:\Users\akash kumar\Downloads\abhay_llm\rag-project"
```

3. Create `.env` file from template:
```powershell
Copy-Item .env.example .env
```

4. Edit `.env` and set your key:
```env
GEMINI_API_KEY=your_actual_key_here
```

5. Start all services:
```powershell
docker compose up -d --build
```

6. Check container status:
```powershell
docker compose ps
```

7. Verify API health:
```powershell
curl.exe -s http://localhost:8000/health
```

Expected:
```json
{"status":"ok","service":"rag-api"}
```

8. Open Swagger UI:
- http://localhost:8000/docs

## 4. API Endpoints

- `POST /api/v1/documents/upload`  
  Upload one file.

- `POST /api/v1/documents/upload-multiple`  
  Upload multiple files in one request.

- `GET /api/v1/documents`  
  List documents.

- `GET /api/v1/documents/{document_id}`  
  Document detail + chunk metadata.

- `GET /api/v1/jobs/{job_id}`  
  Ingestion job status.

- `POST /api/v1/query`  
  Ask question against uploaded documents.

- `DELETE /api/v1/documents/{document_id}`  
  Delete document and related vectors.

## 5. Usage Examples

### Single upload
```powershell
curl.exe -X POST http://localhost:8000/api/v1/documents/upload `
  -F "file=@C:\path\to\file1.pdf"
```

### Multi upload
```powershell
curl.exe -X POST http://localhost:8000/api/v1/documents/upload-multiple `
  -F "files=@C:\path\to\file1.pdf" `
  -F "files=@C:\path\to\file2.pdf" `
  -F "files=@C:\path\to\file3.txt"
```

### Poll ingestion job
```powershell
curl.exe -s http://localhost:8000/api/v1/jobs/<job_id>
```

Wait until `status` is `completed`.

### Query across all uploaded documents
```powershell
curl.exe -X POST http://localhost:8000/api/v1/query `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"Summarize the uploaded documents\"}"
```

### Query only specific documents
```powershell
curl.exe -X POST http://localhost:8000/api/v1/query `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"What are the key findings?\",\"document_ids\":[\"<doc_id_1>\",\"<doc_id_2>\"],\"top_k\":5}"
```

## 6. Limits

- Max documents: `20`
- Max pages per document: `1000`
- Max upload size per file: `MAX_FILE_SIZE_MB` (default `500`)
- Supported file types: `.pdf`, `.docx`, `.txt`, `.md`

## 7. Gemini Embedding Compatibility Note

If your account/API version does not support one embedding model, the service now automatically falls back through compatible embedding model names.

You can still set:
```env
GEMINI_EMBED_MODEL=text-embedding-004
```

## 8. Run Tests

```powershell
python -m pytest tests -v --tb=short
```

## 9. Useful Commands

```powershell
docker compose logs -f api
docker compose logs -f worker
docker compose down
```

## 10. Troubleshooting

- If Docker commands fail with engine/pipe errors: start Docker Desktop.
- If query fails with embedding model error: check API key, then restart:
```powershell
docker compose restart api worker
```
- If services are unhealthy:
```powershell
docker compose ps
docker compose logs --tail=200
```
