"""ModelVersion — tracks trained model versions for the retraining feedback loop."""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime, timezone
from backend.app.db.base import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    model_type = Column(String, nullable=False, default="awc135")
    model_path = Column(String, nullable=True)
    base_model = Column(String, nullable=True)
    training_samples = Column(Integer, default=0)
    corrections_included = Column(Integer, default=0)
    validation_accuracy = Column(Float, nullable=True)
    is_active = Column(Boolean, default=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<ModelVersion(id={self.id}, name='{self.name}', active={self.is_active})>"
