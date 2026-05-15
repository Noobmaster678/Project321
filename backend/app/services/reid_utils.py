"""Shared helpers for quoll-specific re-ID filtering."""
from __future__ import annotations

from sqlalchemy import or_

from backend.app.config import settings
from backend.app.models.detection import Detection


def species_is_quoll(species: str | None) -> bool:
    """Return True when the species string should be treated as a quoll."""
    if not species:
        return False
    species_lc = species.lower()
    if "quoll" in species_lc:
        return True
    target = (settings.TARGET_SPECIES or "").lower().strip()
    return bool(target and target in species_lc)


def quoll_sql_filter():
    """SQLAlchemy filter expression matching quoll detections."""
    parts = [Detection.species.ilike("%quoll%")]
    target = (settings.TARGET_SPECIES or "").strip()
    if target:
        parts.append(Detection.species.ilike(f"%{target}%"))
    return or_(*parts)
