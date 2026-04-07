from pydantic import BaseModel, Field
from typing import Optional, Literal
from uuid import UUID
from datetime import datetime


class SubmissionCreate(BaseModel):
    """Request schema for creating a new submission."""
    text: str = Field(
        ...,
        min_length=1,
        max_length=1024 * 64,
        description="Raw text content to be processed by the LLM pipeline.",
        examples=["The service is working exceptionally well and the performance is fast!"],
    )
    webhook_url: Optional[str] = Field(
        None,
        description="Optional callback URL — receives a POST notification when processing completes or fails.",
        examples=["https://webhook.site/my-hook"],
    )


class LLMOutput(BaseModel):
    """Schema that strictly validates the LLM's JSON response structure."""
    sentiment: Literal["positive", "negative", "neutral"]
    topic: str
    summary: str


class SubmissionResponse(BaseModel):
    """Response schema returned immediately after submitting content."""
    submission_id: UUID
    status: Literal["queued"] = "queued"


class SubmissionStatusResponse(BaseModel):
    """Full response schema for checking submission status and results."""
    id: UUID
    status: Literal["queued", "processing", "completed", "failed"]
    result: Optional[LLMOutput] = None
    error_reason: Optional[str] = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True