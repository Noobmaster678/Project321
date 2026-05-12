"""Tests for MegaDescriptor Re-ID backfill safety."""
import sys
import types

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.models.image import Image
from backend.app.services.reid_backfill import MEGAD_ANNOTATOR, run_reid_backfill


async def _create_quoll_detection(db: AsyncSession, index: int) -> Detection:
    img = Image(
        filename=f"quoll_{index}.jpg",
        file_path=f"images/quoll_{index}.jpg",
    )
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
        species="Spotted-tailed Quoll",
        classification_confidence=0.95,
        crop_path=f"crops/quoll_{index}.jpg",
    )
    db.add(det)
    await db.flush()
    return det


@pytest.mark.asyncio
async def test_refresh_auto_only_deletes_annotations_in_limited_batch(db: AsyncSession, tmp_path, monkeypatch):
    gallery = tmp_path / "gallery.pt"
    gallery.write_bytes(b"fake gallery")
    crops_dir = tmp_path / "crops"
    crops_dir.mkdir()

    dets = []
    for index in range(3):
        det = await _create_quoll_detection(db, index)
        (tmp_path / det.crop_path).write_bytes(b"fake crop")
        db.add(
            Annotation(
                detection_id=det.id,
                annotator=MEGAD_ANNOTATOR,
                individual_id=f"old-{index}",
            )
        )
        dets.append(det)
    await db.commit()

    fake_reid = types.ModuleType("backend.worker.pipelines.megadescriptor_reid")

    def predict_crop(crop_abs, gallery_path, sim_threshold, gap_threshold):
        return f"new-{crop_abs.stem}", {"s1": 0.9, "gap": 0.2}

    fake_reid.predict_crop = predict_crop
    monkeypatch.setitem(sys.modules, "backend.worker.pipelines.megadescriptor_reid", fake_reid)
    monkeypatch.setattr("backend.app.services.reid_backfill.reid_gallery_path", lambda: gallery)
    monkeypatch.setattr("backend.app.services.reid_backfill.settings.STORAGE_ROOT", tmp_path)

    stats = await run_reid_backfill(db, mode="refresh_auto", limit=2)
    await db.commit()

    anns = (
        await db.execute(select(Annotation).order_by(Annotation.detection_id, Annotation.id))
    ).scalars().all()

    assert stats["candidates"] == 2
    assert stats["removed_auto"] == 2
    assert stats["assigned"] == 2
    assert [(ann.detection_id, ann.individual_id) for ann in anns] == [
        (dets[0].id, "new-quoll_0"),
        (dets[1].id, "new-quoll_1"),
        (dets[2].id, "old-2"),
    ]
