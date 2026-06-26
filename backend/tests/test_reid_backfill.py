"""Regression tests for re-ID backfill data integrity."""
import sys
import types

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.annotation import Annotation
from backend.app.services.reid_backfill import MEGAD_ANNOTATOR, run_reid_backfill


@pytest.mark.asyncio
async def test_refresh_auto_only_removes_limited_candidate_batch(
    db: AsyncSession,
    sample_data,
    tmp_path,
    monkeypatch,
):
    storage_root = tmp_path / "storage"
    crops_dir = storage_root / "crops"
    crops_dir.mkdir(parents=True)
    gallery_path = tmp_path / "gallery.pt"
    gallery_path.write_bytes(b"fake gallery")

    monkeypatch.setattr(settings, "STORAGE_ROOT", storage_root)
    monkeypatch.setattr(settings, "REID_GALLERY_PATH", gallery_path)

    for idx, det in enumerate(sample_data["detections"], start=1):
        det.species = "Dasyurus sp | Quoll sp"
        det.crop_path = f"crops/{idx}.jpg"
        (storage_root / det.crop_path).write_bytes(b"fake crop")
        db.add(
            Annotation(
                detection_id=det.id,
                annotator=MEGAD_ANNOTATOR,
                individual_id=f"old-{idx}",
            )
        )
    await db.commit()

    def fake_predict_crop(*_args, **_kwargs):
        return "new-id", {"s1": 0.9, "gap": 0.2}

    monkeypatch.setitem(
        sys.modules,
        "backend.worker.pipelines.megadescriptor_reid",
        types.SimpleNamespace(predict_crop=fake_predict_crop),
    )

    stats = await run_reid_backfill(db, mode="refresh_auto", limit=2)
    await db.commit()

    assert stats["removed_auto"] == 2
    assert stats["assigned"] == 2

    rows = (
        await db.execute(
            select(Annotation.detection_id, Annotation.individual_id)
            .where(Annotation.annotator == MEGAD_ANNOTATOR)
            .order_by(Annotation.detection_id, Annotation.id)
        )
    ).all()
    assert rows == [
        (sample_data["detections"][0].id, "new-id"),
        (sample_data["detections"][1].id, "new-id"),
        (sample_data["detections"][2].id, "old-3"),
    ]
