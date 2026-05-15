"""Tests for the MegaDescriptor re-ID backfill service."""
import sys
import types
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.models.image import Image
from backend.app.services.reid_backfill import MEGAD_ANNOTATOR, run_reid_backfill


@pytest.mark.asyncio
async def test_refresh_auto_limit_preserves_annotations_outside_window(
    db: AsyncSession,
    tmp_path,
    monkeypatch,
):
    storage_root = tmp_path / "storage"
    crops_dir = storage_root / "crops"
    crops_dir.mkdir(parents=True)
    gallery_path = tmp_path / "gallery.pt"
    gallery_path.write_bytes(b"fake gallery")

    monkeypatch.setattr(settings, "STORAGE_ROOT", storage_root)
    monkeypatch.setattr(
        "backend.app.services.reid_backfill.reid_gallery_path",
        lambda: gallery_path,
    )

    fake_reid = types.ModuleType("backend.worker.pipelines.megadescriptor_reid")

    def fake_predict_crop(*_args, **_kwargs):
        return "new-individual", {"s1": 0.91, "gap": 0.22}

    fake_reid.predict_crop = fake_predict_crop
    monkeypatch.setitem(sys.modules, "backend.worker.pipelines.megadescriptor_reid", fake_reid)

    detections = []
    for idx in range(3):
        crop_rel = f"crops/quoll-{idx}.jpg"
        (storage_root / crop_rel).write_bytes(b"crop")
        image = Image(
            filename=f"IMG_{idx}.JPG",
            file_path=f"images/IMG_{idx}.JPG",
            processed=True,
            has_animal=True,
            captured_at=datetime(2024, 1, idx + 1, tzinfo=timezone.utc),
        )
        db.add(image)
        await db.flush()

        detection = Detection(
            image_id=image.id,
            bbox_x=0.1,
            bbox_y=0.2,
            bbox_w=0.3,
            bbox_h=0.4,
            detection_confidence=0.95,
            category="animal",
            species="Dasyurus sp | Quoll sp",
            classification_confidence=0.89,
            crop_path=crop_rel,
        )
        db.add(detection)
        await db.flush()
        detections.append(detection)

        db.add(
            Annotation(
                detection_id=detection.id,
                annotator=MEGAD_ANNOTATOR,
                individual_id=f"old-individual-{idx}",
            )
        )
    await db.commit()

    stats = await run_reid_backfill(db, mode="refresh_auto", limit=1)
    await db.commit()

    assert stats["removed_auto"] == 1
    assert stats["assigned"] == 1

    rows = (
        await db.execute(
            select(Annotation.detection_id, Annotation.individual_id)
            .where(Annotation.detection_id.in_([det.id for det in detections]))
            .order_by(Annotation.detection_id)
        )
    ).all()

    assert rows == [
        (detections[0].id, "new-individual"),
        (detections[1].id, "old-individual-1"),
        (detections[2].id, "old-individual-2"),
    ]
