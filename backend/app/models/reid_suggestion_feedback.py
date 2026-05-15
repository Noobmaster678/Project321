"""Persisted top-k re-ID suggestion impressions and outcomes."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from backend.app.db.base import Base


class ReidSuggestionFeedback(Base):
    __tablename__ = "reid_suggestion_feedback"

    id = Column(Integer, primary_key=True, index=True)
    detection_id = Column(Integer, ForeignKey("detections.id"), nullable=False, index=True)
    suggested_individual_id = Column(String, nullable=False, index=True)
    rank = Column(Integer, nullable=False)
    similarity = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)
    accepted_by_gate = Column(Boolean, nullable=False, default=False)
    shown_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    resolved = Column(Boolean, nullable=False, default=False)
    chosen_individual_id = Column(String, nullable=True)
    accepted = Column(Boolean, nullable=True)
    annotator = Column(String, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
