"""Backfill MegaDescriptor re-ID annotations on existing quoll detections (no MegaDetector re-run)."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import reid_gallery_path, settings
from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.services.reid_utils import species_is_quoll, quoll_sql_filter

MEGAD_ANNOTATOR = "megadescriptor_reid"
logger = logging.getLogger(__name__)


async def run_reid_backfill(
    db: AsyncSession,
    *,
    mode: str,
    limit: int,
    refresh_gallery: bool = False,
) -> dict:
    """
    mode:
      missing_only — same as upload pipeline: only detections with zero annotations.
      refresh_auto — delete megadescriptor_reid rows for quoll crops, then re-infer unless a
                     non-auto annotation already sets individual_id (manual ID preserved).
    """
    if mode not in ("missing_only", "refresh_auto"):
        raise ValueError("mode must be missing_only or refresh_auto")

    gallery = reid_gallery_path()
    if not gallery.is_file():
        raise ValueError(f"Re-ID gallery not found at {gallery}")

    try:
        from backend.worker.pipelines.megadescriptor_reid import predict_crop
    except ImportError as e:
        raise ValueError(f"Re-ID dependencies missing (timm/torch): {e}") from e

    stats: dict[str, int] = {
        "candidates": 0,
        "assigned": 0,
        "unknown": 0,
        "skipped": 0,
        "errors": 0,
        "removed_auto": 0,
    }

    base_filter = and_(
        Detection.crop_path.isnot(None),
        Detection.crop_path != "",
        quoll_sql_filter(),
    )

    if mode == "refresh_auto":
        res = await db.execute(
            delete(Annotation).where(
                Annotation.annotator == MEGAD_ANNOTATOR,
                Annotation.detection_id.in_(select(Detection.id).where(base_filter)),
            )
        )
        stats["removed_auto"] = int(res.rowcount or 0)
        await db.flush()

    q = select(Detection).where(base_filter).order_by(Detection.id).limit(limit)
    dets = (await db.execute(q)).scalars().all()

    for det in dets:
        stats["candidates"] += 1
        if not species_is_quoll(det.species):
            stats["skipped"] += 1
            continue

        crop_abs: Path = settings.STORAGE_ROOT / det.crop_path
        if not crop_abs.is_file():
            stats["skipped"] += 1
            continue

        ann_result = await db.execute(select(Annotation).where(Annotation.detection_id == det.id))
        anns = ann_result.scalars().all()

        if mode == "missing_only":
            if len(anns) > 0:
                stats["skipped"] += 1
                continue
        else:
            manual_id = any(
                bool(a.individual_id) and (a.annotator or "") != MEGAD_ANNOTATOR for a in anns
            )
            if manual_id:
                stats["skipped"] += 1
                continue

        try:
            iid, meta = await asyncio.to_thread(
                predict_crop,
                crop_abs,
                gallery,
                settings.REID_SIM_THRESHOLD,
                settings.REID_GAP_THRESHOLD,
            )
        except Exception:
            logger.exception("Re-ID backfill failed for detection %s", det.id)
            stats["errors"] += 1
            continue

        if not iid:
            stats["unknown"] += 1
            continue

        s1 = float(meta.get("s1", 0.0))
        gap = float(meta.get("gap", 0.0))
        db.add(
            Annotation(
                detection_id=det.id,
                annotator=MEGAD_ANNOTATOR,
                individual_id=iid,
                notes=f"backfill sim={s1:.3f} gap={gap:.3f}",
            )
        )
        stats["assigned"] += 1

    if refresh_gallery:
        from backend.app.services.reid_learning import rebuild_gallery_from_confirmed_annotations

        stats.update(await rebuild_gallery_from_confirmed_annotations(db))

    return stats
