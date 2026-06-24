"""Tests for MegaDescriptor re-ID backfill safety."""
import sys
import types

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.models.image import Image
from backend.app.services import reid_backfill


@pytest.mark.asyncio
async def test_refresh_auto_deletes_only_limited_candidates(
    db: AsyncSession,
    tmp_path,
    monkeypatch,
):
    gallery = tmp_path / "gallery.pt"
    gallery.write_bytes(b"test-gallery")
    monkeypatch.setattr(reid_backfill, "reid_gallery_path", lambda: gallery)
    monkeypatch.setattr(reid_backfill.settings, "STORAGE_ROOT", tmp_path)

    fake_pipeline = types.ModuleType("backend.worker.pipelines.megadescriptor_reid")
    fake_pipeline.predict_crop = lambda *args: ("02QNEW", {"s1": 0.91, "gap": 0.2})
    monkeypatch.setitem(sys.modules, "backend.worker.pipelines.megadescriptor_reid", fake_pipeline)

    det_ids: list[int] = []
    for idx in range(3):
        crop_rel = f"crops/quoll-{idx}.jpg"
        crop_abs = tmp_path / crop_rel
        crop_abs.parent.mkdir(parents=True, exist_ok=True)
        crop_abs.write_bytes(b"crop")

        img = Image(filename=f"img-{idx}.jpg", file_path=f"img-{idx}.jpg", processed=True, has_animal=True)
        db.add(img)
        await db.flush()
        det = Detection(
            image_id=img.id,
            bbox_x=0.1,
            bbox_y=0.2,
            bbox_w=0.3,
            bbox_h=0.4,
            detection_confidence=0.9,
            category="animal",
            species="Dasyurus sp | Quoll sp",
            classification_confidence=0.95,
            model_version="test",
            crop_path=crop_rel,
        )
        db.add(det)
        await db.flush()
        det_ids.append(det.id)
        db.add(
            Annotation(
                detection_id=det.id,
                annotator=reid_backfill.MEGAD_ANNOTATOR,
                individual_id=f"02QOLD{idx}",
            )
        )
    await db.commit()

    stats = await reid_backfill.run_reid_backfill(db, mode="refresh_auto", limit=1)
    await db.commit()

    rows = (
        await db.execute(
            select(Annotation).where(Annotation.annotator == reid_backfill.MEGAD_ANNOTATOR)
        )
    ).scalars().all()
    by_detection = {row.detection_id: row.individual_id for row in rows}

    assert stats["removed_auto"] == 1
    assert by_detection[det_ids[0]] == "02QNEW"
    assert by_detection[det_ids[1]] == "02QOLD1"
    assert by_detection[det_ids[2]] == "02QOLD2"
