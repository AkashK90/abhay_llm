"""
main.py
FastAPI application factory.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import setup_logging
from app.core.exceptions import register_exception_handlers
from app.api.v1 import v1_router

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    import logging

    logger = logging.getLogger(__name__)
    settings = get_settings()

    # Ensure storage directory exists
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
    logger.info("Storage dir ready: %s", settings.storage_dir)

    # Warm up Chroma connection (fail fast on misconfiguration)
    try:
        from app.services.vector_store import get_vector_store

        get_vector_store()
        logger.info("ChromaDB connection OK")
    except Exception as exc:
        logger.warning("ChromaDB not ready at startup: %s", exc)

    yield

    logger.info("Shutting down RAG API")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="RAG Pipeline API",
        description=(
            "Retrieval-Augmented Generation pipeline. "
            "Upload documents, then query them with natural language."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(v1_router)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "ok", "service": "rag-api"}

    return app


app = create_app()
