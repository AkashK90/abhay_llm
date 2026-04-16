"""
celery_app.py
Celery application factory.
Keep this module import-side-effect-free so it can be imported by
both the FastAPI process and the worker process safely.
"""
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rag_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks.ingestion"],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Reliability
    task_acks_late=True,               # ack only after task completes
    task_reject_on_worker_lost=True,   # re-queue if worker dies mid-task
    worker_prefetch_multiplier=1,      # one task at a time per worker thread
    # Retries
    task_max_retries=3,
    task_default_retry_delay=10,       # seconds
    # Result TTL
    result_expires=86400,              # 24 h
    # Routing — single queue for now, easy to split later
    task_default_queue="ingestion",
    task_queues={
        "ingestion": {"exchange": "ingestion", "routing_key": "ingestion"},
    },
)
