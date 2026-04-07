from sqlalchemy import Column, String, JSON, DateTime, Integer, func, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.database import Base


class Submission(Base):
    __tablename__ = "submissions"

    # ── Primary Key ──────────────────────────────────────────
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # ── Input ────────────────────────────────────────────────
    text = Column(Text, nullable=False)

    # ── Pipeline State ───────────────────────────────────────
    status = Column(String, default="queued", index=True)  # queued | processing | completed | failed
    result_json = Column(JSON, nullable=True)               # validated LLM output
    error_reason = Column(String, nullable=True)

    # ── Retry Tracking ───────────────────────────────────────
    retry_count = Column(Integer, default=0)

    # ── Timestamps ───────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Observability Metadata ───────────────────────────────
    processing_time = Column(String, nullable=True)  # Total worker duration
    llm_latency = Column(String, nullable=True)       # Raw LLM API call time