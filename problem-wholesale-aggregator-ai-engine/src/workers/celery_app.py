from celery import Celery
from src.config.settings import settings

# 1. Initialize Celery App
worker_app= Celery(
    "batchprocure_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# 2. High-Performance Configuration
worker_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True, #By default, Celery deletes a task from Redis the millisecond it starts. If your worker crashes during an AI execution, that order is gone forever. Late ack means Celery only deletes the task after it successfully finishes.
    worker_prefetch_multiplier=1, #Heavy tasks (like LLM text-generation and vector matching) should be run one at a time. This prevents RAM exhaustion in high-concurrency environments.
)

# 3. Discover tasks automatically
worker_app.autodiscover_tasks(["src.workers"])