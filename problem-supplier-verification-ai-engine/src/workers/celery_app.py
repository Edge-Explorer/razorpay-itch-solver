from celery import Celery
from src.config.settings import settings

worker_app= Celery(
    "supplier_verification_worker",
    broker= settings.REDIS_URL,  # Where tasks are sent
    backend= settings.REDIS_URL, # Where results are stored
    include= ["src.workers.tasks"]  # Where our actual task code will live
)

worker_app.conf.update(
    task_serializer= "json",
    accept_content= ["json"],
    result_serializer= "json",
    timezone= "UTC",
    enable_utc= True,  # This prevents one bad AI task from blocking all other workers.
    task_acks_late= True,
    worker_prefetch_multiplier= 1
)

if __name__ == "__main__":
    worker_app.start()