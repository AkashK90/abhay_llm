.PHONY: help up down build logs test test-unit test-integration shell-api shell-worker migrate seed clean

# ── Config ────────────────────────────────────────────────────────────────────
DC = docker compose
APP = rag-pipeline

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker ────────────────────────────────────────────────────────────────────
up: ## Start all services in the background
	$(DC) up -d --build

down: ## Stop all services
	$(DC) down

build: ## Rebuild images without starting
	$(DC) build

restart: ## Restart all services
	$(DC) restart

logs: ## Tail all service logs
	$(DC) logs -f

logs-api: ## Tail FastAPI logs only
	$(DC) logs -f api

logs-worker: ## Tail Celery worker logs only
	$(DC) logs -f worker

# ── Database ─────────────────────────────────────────────────────────────────
migrate: ## Run Alembic migrations inside the running api container
	$(DC) exec api alembic upgrade head

migrate-create: ## Create new migration (usage: make migrate-create MSG="add table")
	$(DC) exec api alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Roll back one migration
	$(DC) exec api alembic downgrade -1

# ── Testing ───────────────────────────────────────────────────────────────────
test: ## Run full test suite with coverage
	$(DC) run --rm api pytest tests/ -v --cov=app --cov=ingestion --cov-report=term-missing

test-unit: ## Run unit tests only
	$(DC) run --rm api pytest tests/unit/ -v

test-integration: ## Run integration tests only
	$(DC) run --rm api pytest tests/integration/ -v

test-local: ## Run tests locally (requires local venv)
	pytest tests/ -v --tb=short

# ── Development ───────────────────────────────────────────────────────────────
shell-api: ## Open bash shell in the api container
	$(DC) exec api bash

shell-worker: ## Open bash shell in the worker container
	$(DC) exec worker bash

shell-db: ## Open psql session
	$(DC) exec postgres psql -U $${POSTGRES_USER:-raguser} -d $${POSTGRES_DB:-ragdb}

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean: ## Remove all containers, volumes, and local data
	$(DC) down -v --remove-orphans
	rm -rf storage/* chroma_data/* htmlcov .coverage test_rag.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

clean-storage: ## Delete only uploaded files (keep DB and vectors)
	rm -rf storage/*

reset-vectors: ## Reset ChromaDB collection (via API)
	curl -X DELETE http://localhost:8001/api/v1/collections/$${CHROMA_COLLECTION:-rag_documents} || true

# ── Local dev without Docker ──────────────────────────────────────────────────
install: ## Install Python deps in the current virtualenv
	pip install -r requirements.txt

dev-api: ## Run FastAPI in dev mode locally
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker: ## Run Celery worker locally
	celery -A app.workers.celery_app.celery_app worker --loglevel=info --concurrency=2 --queues=ingestion
