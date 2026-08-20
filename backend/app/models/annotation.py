"""Annotation model — human review/correction of a detection."""
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, index=True)
    detection_id = Column(Integer, ForeignKey("detections.id"), nullable=False, index=True)
    annotator = Column(String, nullable=True)
    corrected_species = Column(String, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    notes = Column(String, nullable=True)
    individual_id = Column(String, nullable=True)
    flag_for_retraining = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    detection = relationship("Detection", back_populates="annotations")

    def __repr__(self):
        return f"<Annotation(id={self.id}, detection_id={self.detection_id}, is_correct={self.is_correct})>"


def _annotation_sort_key(ann: Annotation) -> tuple[datetime, int]:
    ts = ann.created_at or datetime.min.replace(tzinfo=timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (ts, int(ann.id or 0))


def merge_annotation_review_fields(annotations: Sequence[Annotation] | None) -> dict[str, Any]:
    """Collapse multiple annotation rows into the effective review state.

    Review writes species verdicts and individual IDs as separate rows (auto
    re-ID first, then a human correction/assignment). Callers that only read
    ``annotations[0]`` silently drop the later row.
    """
    merged: dict[str, Any] = {
        "is_correct": None,
        "corrected_species": None,
        "notes": None,
        "individual_id": None,
        "flag_for_retraining": None,
    }
    if not annotations:
        return merged

    flag = False
    saw_flag = False
    for ann in sorted(annotations, key=_annotation_sort_key):
        if ann.is_correct is not None:
            merged["is_correct"] = ann.is_correct
        if ann.corrected_species is not None:
            merged["corrected_species"] = ann.corrected_species
        if ann.notes is not None:
            merged["notes"] = ann.notes
        if ann.individual_id:
            merged["individual_id"] = ann.individual_id
        if ann.flag_for_retraining is not None:
            saw_flag = True
            flag = flag or bool(ann.flag_for_retraining)
    if saw_flag:
        merged["flag_for_retraining"] = flag
    return merged
