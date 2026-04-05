"""Deployment model — a camera placed at a location for a specific date range."""
from sqlalchemy import Column, Integer, String, Date, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.app.db.base import Base


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True, index=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    elevation = Column(Float, nullable=True)
    setup_notes = Column(String, nullable=True)
    bait_used = Column(Boolean, default=False)
    trap_nights = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    camera = relationship("Camera", backref="deployments")
    collection = relationship("Collection", backref="deployments")

    def __repr__(self):
        return f"<Deployment(id={self.id}, camera_id={self.camera_id}, {self.start_date} to {self.end_date})>"
