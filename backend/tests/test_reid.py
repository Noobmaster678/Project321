"""Tests for re-ID suggestion and backfill safety."""
import sys
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.models.image import Image
from backend.app.services.reid_backfill import MEGAD_ANNOTATOR, run_reid_backfill
from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_reid_suggestions_requires_auth(client: AsyncClient):
    resp = await client.get("/api/reid/detections/1/suggestions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reid_suggestions_auth_checks_before_inference(client: AsyncClient, test_user):
    resp = await client.get(
        "/api/reid/detections/9999/suggestions",
        headers=auth_header(test_user),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_refresh_auto_only_deletes_limited_backfill_batch(
    db: AsyncSession,
    tmp_path,
    monkeypatch,
):
    storage_root = tmp_path / "storage"
    crop_dir = storage_root / "crops"
    crop_dir.mkdir(parents=True)
    gallery_path = tmp_path / "gallery.pt"
    gallery_path.write_bytes(b"fake gallery")

    detections = []
    for idx in range(4):
        crop_path = f"crops/crop_{idx}.jpg"
        (storage_root / crop_path).write_bytes(b"fake crop")
        image = Image(filename=f"img_{idx}.jpg", file_path=f"images/img_{idx}.jpg")
        db.add(image)
        await db.flush()
        detection = Detection(
            image_id=image.id,
            bbox_x=0.1,
            bbox_y=0.2,
            bbox_w=0.3,
            bbox_h=0.4,
            detection_confidence=0.9,
            category="animal",
            species="Dasyurus sp | Quoll sp",
            classification_confidence=0.95,
            crop_path=crop_path,
        )
        db.add(detection)
        await db.flush()
        detections.append(detection)
        db.add(
            Annotation(
                detection_id=detection.id,
                annotator=MEGAD_ANNOTATOR,
                individual_id=f"old_{idx}",
            )
        )
    await db.commit()

    monkeypatch.setattr(
        "backend.app.services.reid_backfill.reid_gallery_path",
        lambda: gallery_path,
    )
    monkeypatch.setattr(
        "backend.app.services.reid_backfill.settings.STORAGE_ROOT",
        storage_root,
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.worker.pipelines.megadescriptor_reid",
        SimpleNamespace(predict_crop=lambda *_args, **_kwargs: ("new_id", {"s1": 0.9, "gap": 0.2})),
    )

    stats = await run_reid_backfill(db, mode="refresh_auto", limit=2)

    assert stats["removed_auto"] == 2
    total_auto = (
        await db.execute(
            select(func.count(Annotation.id)).where(Annotation.annotator == MEGAD_ANNOTATOR)
        )
    ).scalar_one()
    assert total_auto == 4

    untouched_ids = [det.id for det in detections[2:]]
    remaining_old = (
        await db.execute(
            select(func.count(Annotation.id)).where(
                Annotation.detection_id.in_(untouched_ids),
                Annotation.annotator == MEGAD_ANNOTATOR,
                Annotation.individual_id.like("old_%"),
            )
        )
    ).scalar_one()
    assert remaining_old == 2
