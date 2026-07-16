"""Re-ID learning helpers: suggestion telemetry, incremental updates, and rebuilds."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import reid_gallery_path, settings
from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.models.reid_suggestion_feedback import ReidSuggestionFeedback

AUTO_REID_ANNOTATOR = "megadescriptor_reid"


async def log_reid_suggestions(
    db: AsyncSession,
    detection_id: int,
    suggestions: list[dict],
) -> None:
    """Persist one suggestion impression row per ranked candidate."""
    await db.execute(
        delete(ReidSuggestionFeedback).where(
            ReidSuggestionFeedback.detection_id == detection_id,
            ReidSuggestionFeedback.resolved == False,  # noqa: E712
        )
    )
    for item in suggestions:
        db.add(
            ReidSuggestionFeedback(
                detection_id=detection_id,
                suggested_individual_id=str(item.get("individual_id", "")),
                rank=int(item.get("rank", 0)),
                similarity=float(item.get("similarity", 0.0)),
                confidence=float(item.get("confidence", 0.0)),
                accepted_by_gate=bool(item.get("accepted_by_gate", False)),
            )
        )
    await db.flush()


async def resolve_reid_suggestions(
    db: AsyncSession,
    detection_id: int,
    chosen_individual_id: str | None,
    annotator: str | None,
) -> None:
    """Mark unresolved suggestion impressions as accepted/rejected after annotation."""
    result = await db.execute(
        select(ReidSuggestionFeedback).where(
            ReidSuggestionFeedback.detection_id == detection_id,
            ReidSuggestionFeedback.resolved == False,  # noqa: E712
        )
    )
    rows = result.scalars().all()
    if not rows:
        return
    now = datetime.now(timezone.utc)
    for row in rows:
        row.resolved = True
        row.chosen_individual_id = chosen_individual_id
        row.annotator = annotator
        row.accepted = bool(chosen_individual_id and row.suggested_individual_id == chosen_individual_id)
        row.resolved_at = now
    await db.flush()


def _iter_confirmed_detection_rows(rows: list[tuple[Detection, Annotation]]) -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for det, ann in rows:
        if not ann.individual_id or not det.crop_path:
            continue
        crop_abs = settings.STORAGE_ROOT / det.crop_path
        if not crop_abs.is_file():
            continue
        items.append((ann.individual_id, crop_abs))
    return items


async def incremental_update_from_detection(db: AsyncSession, detection_id: int, individual_id: str) -> bool:
    """Apply immediate lightweight prototype update using one confirmed crop."""
    try:
        from backend.worker.pipelines.megadescriptor_reid import embed_crop, incremental_update_gallery
    except ImportError:
        return False

    det = (await db.execute(select(Detection).where(Detection.id == detection_id))).scalar_one_or_none()
    if not det or not det.crop_path:
        return False
    crop_abs = settings.STORAGE_ROOT / det.crop_path
    gallery = reid_gallery_path()
    if not crop_abs.is_file() or not gallery.is_file():
        return False
    embedding = embed_crop(crop_abs, gallery)
    if embedding is None:
        return False
    return incremental_update_gallery(gallery, individual_id, embedding)


async def remove_individual_from_reid_gallery(individual_id: str) -> bool:
    """Remove a deleted individual from the automatic re-ID checkpoint."""
    gallery = reid_gallery_path()
    if not gallery.is_file():
        return True
    try:
        from backend.worker.pipelines.megadescriptor_reid import remove_individual_from_gallery
    except ImportError:
        return False
    return await asyncio.to_thread(remove_individual_from_gallery, gallery, individual_id)


async def rebuild_gallery_from_confirmed_annotations(db: AsyncSession) -> dict[str, int]:
    """Rebuild gallery prototypes from manual confirmed IDs (scheduled/manual path)."""
    try:
        from backend.worker.pipelines.megadescriptor_reid import embed_crop, incremental_update_gallery
    except ImportError as exc:
        raise ValueError(f"Re-ID dependencies missing: {exc}") from exc

    rows = (
        await db.execute(
            select(Detection, Annotation)
            .join(Annotation, Annotation.detection_id == Detection.id)
            .where(
                Annotation.individual_id.isnot(None),
                Detection.crop_path.isnot(None),
                Annotation.annotator != AUTO_REID_ANNOTATOR,
            )
            .order_by(Annotation.created_at.asc())
        )
    ).all()
    pairs = _iter_confirmed_detection_rows(rows)
    gallery = reid_gallery_path()
    if not gallery.is_file():
        raise ValueError(f"Re-ID gallery not found at {gallery}")

    updated = 0
    skipped = 0
    for individual_id, crop_abs in pairs:
        emb = embed_crop(crop_abs, gallery)
        if emb is None:
            skipped += 1
            continue
        if incremental_update_gallery(gallery, individual_id, emb):
            updated += 1
        else:
            skipped += 1
    return {"gallery_updates": updated, "gallery_skipped": skipped}
