from celery import Celery
from app.config import settings

celery_app = Celery(
    "ai_pipeline",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)



celery_app.autodiscover_tasks(["app.workers"])