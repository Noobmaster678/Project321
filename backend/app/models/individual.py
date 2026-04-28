"""Individual quoll model — a specific identified animal."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class Individual(Base):
    __tablename__ = "individuals"

    id = Column(Integer, primary_key=True, index=True)
    individual_id = Column(String, unique=True, nullable=False, index=True)  # e.g., "02Q2", "07Q2"
    species = Column(String, nullable=False, default="Spotted-tailed Quoll")
    name = Column(String, nullable=True)  # optional nickname
    first_seen = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    total_sightings = Column(Integer, default=0)

    # Optional reference detections picked by ecologist (left/right profile)
    ref_left_detection_id = Column(Integer, ForeignKey("detections.id"), nullable=True, index=True)
    ref_right_detection_id = Column(Integer, ForeignKey("detections.id"), nullable=True, index=True)

    # Relationships
    sightings = relationship("Sighting", back_populates="individual", lazy="selectin")
    ref_left_detection = relationship("Detection", foreign_keys=[ref_left_detection_id], lazy="selectin")
    ref_right_detection = relationship("Detection", foreign_keys=[ref_right_detection_id], lazy="selectin")

    def __repr__(self):
        return f"<Individual(id={self.id}, individual_id='{self.individual_id}')>"
