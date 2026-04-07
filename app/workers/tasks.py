from celery import shared_task
from app.db.database import SessionLocal
from app.models.submission import Submission
from app.services.llm_service import LLMService
from app.config import settings
import logging
import time
import httpx
from uuid import UUID

logger = logging.getLogger(__name__)

llm_service = LLMService()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=settings.MAX_RETRIES,
)
def process_submission_task(self, submission_id: str, webhook_url: str = None):
    """
    Celery background worker task — processes a single submission through the LLM pipeline.
    """
    db = SessionLocal()
    start_time = time.time()

    try:
        # Convert string ID from Celery back to UUID object for SQLAlchemy
        uid = UUID(submission_id)
        
        # 1. Retrieve submission with row-level lock (prevents race conditions)
        submission = (
            db.query(Submission)
            .with_for_update()
            .filter(Submission.id == uid)
            .first()
        )
        if not submission:
            logger.error(f"Submission {submission_id} not found — aborting task.")
            return

        # Idempotency guard — skip if already completed
        if submission.status == "completed":
            logger.warning(f"Submission {submission_id} already completed — skipping.")
            return

        # Update status to processing
        submission.status = "processing"
        submission.retry_count = self.request.retries
        db.commit()

        # 2. Call LLM Service
        logger.info(
            f"Processing submission {submission_id} "
            f"(attempt {self.request.retries + 1}/{self.max_retries + 1})"
        )
        llm_result = llm_service.process_content(submission.text)

        # 3. Store result in DB
        submission.result_json = llm_result
        submission.llm_latency = llm_result.get("latency", "N/A")

        processing_duration = time.time() - start_time
        submission.processing_time = f"{processing_duration:.3f}s"
        submission.status = "completed"

        db.commit()
        logger.info(f"✅ Successfully processed submission {submission_id} in {processing_duration:.3f}s")

        # 4. Fire Webhook if configured
        if webhook_url:
            _fire_webhook(webhook_url, submission_id)

    except Exception as exc:
        db.rollback()
        logger.error(f"❌ Error processing submission {submission_id}: {type(exc).__name__}: {exc}")

        # Persist error reason in database if we can reach it
        try:
            uid = UUID(submission_id)
            submission = db.query(Submission).filter(Submission.id == uid).first()
            if submission:
                submission.error_reason = f"{type(exc).__name__}: {str(exc)[:500]}"
                submission.retry_count = self.request.retries

                # If we've exhausted all retries, mark as permanently failed
                if self.request.retries >= self.max_retries:
                    submission.status = "failed"
                    logger.error(f"💀 Submission {submission_id} permanently failed after {self.max_retries} retries.")

                    # Fire failure webhook
                    if webhook_url:
                        _fire_webhook(webhook_url, submission_id, status="failed")

                db.commit()
        except Exception as db_exc:
            logger.error(f"Failed to update error state in DB for {submission_id}: {db_exc}")

        # Re-raise to trigger Celery retry
        raise exc
    finally:
        db.close()


def _fire_webhook(url: str, submission_id: str, status: str = "completed"):
    """Best-effort webhook notification — failures are logged but never block the pipeline."""
    try:
        response = httpx.post(
            url,
            json={"submission_id": submission_id, "status": status},
            timeout=5.0,
        )
        logger.info(f"Webhook fired to {url} — HTTP {response.status_code}")
    except Exception as e:
        logger.warning(f"Webhook delivery failed to {url}: {e}")