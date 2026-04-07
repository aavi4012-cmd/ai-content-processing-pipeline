from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from app.db.database import get_db
from app.models.submission import Submission
from app.schemas.submission_schema import (
    SubmissionCreate,
    SubmissionResponse,
    SubmissionStatusResponse,
)
from app.queue.celery_app import celery_app

router = APIRouter()


@router.post(
    "/submit",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit content for AI processing",
    description="Accepts raw text, persists it, and queues it for asynchronous LLM enrichment.",
)
def submit_content(
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
):
    # 1. Persist submission
    new_submission = Submission(text=payload.text, status="queued")
    db.add(new_submission)
    db.commit()
    db.refresh(new_submission)

    # 2. Dispatch to Celery worker
    celery_app.send_task(
        "app.workers.tasks.process_submission_task",
        kwargs={
            "submission_id": str(new_submission.id),
            "webhook_url": payload.webhook_url,
        },
    )

    # 3. Return immediately with submission ID
    return SubmissionResponse(submission_id=new_submission.id)


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionStatusResponse,
    summary="Get submission status",
    description="Retrieve the current processing status and results of a specific submission.",
)
def get_submission_status(
    submission_id: UUID,
    db: Session = Depends(get_db),
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found.",
        )

    return _map_to_response(submission)


@router.get(
    "/submissions",
    response_model=List[SubmissionStatusResponse],
    summary="List all submissions",
    description="Returns a paginated list of all submissions, optionally filtered by status.",
)
def list_submissions(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status: queued, processing, completed, failed",
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
    db: Session = Depends(get_db),
):
    query = db.query(Submission)

    if status_filter:
        query = query.filter(Submission.status == status_filter)

    submissions = query.order_by(Submission.created_at.desc()).offset(skip).limit(limit).all()
    return [_map_to_response(s) for s in submissions]


def _map_to_response(submission: Submission) -> SubmissionStatusResponse:
    """Maps a SQLAlchemy model to the Pydantic response schema."""
    return SubmissionStatusResponse(
        id=submission.id,
        status=submission.status,
        result=submission.result_json,
        error_reason=submission.error_reason,
        retry_count=submission.retry_count or 0,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
    )