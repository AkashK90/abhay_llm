from fastapi import APIRouter

from app.api.v1.documents import router as documents_router, job_router
from app.api.v1.query import router as query_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(documents_router)
v1_router.include_router(job_router)
v1_router.include_router(query_router)
