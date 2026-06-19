"""Regression tests for MegaDescriptor re-ID backfill behavior."""
import sys
import types

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.services import reid_backfill


def _install_fake_reid_model(monkeypatch, individual_id: str = "NEW-Q1") -> None:
    fake_module = types.ModuleType("backend.worker.pipelines.megadescriptor_reid")

    def predict_crop(*_args, **_kwargs):
        return individual_id, {"s1": 0.91, "gap": 0.27}

    fake_module.predict_crop = predict_crop
    monkeypatch.setitem(sys.modules, "backend.worker.pipelines.megadescriptor_reid", fake_module)


async def _prepare_crop_backfill(monkeypatch, tmp_path) -> None:
    gallery = tmp_path / "gallery.pt"
    gallery.write_bytes(b"fake gallery")
    (tmp_path / "crops").mkdir()
    monkeypatch.setattr(settings, "STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(reid_backfill, "reid_gallery_path", lambda: gallery)
    _install_fake_reid_model(monkeypatch)


@pytest.mark.asyncio
async def test_refresh_auto_only_removes_annotations_for_limited_candidates(
    db: AsyncSession,
    sample_data,
    tmp_path,
    monkeypatch,
):
    await _prepare_crop_backfill(monkeypatch, tmp_path)

    first_det = sample_data["detections"][0]
    first_det.crop_path = "crops/first.jpg"
    (tmp_path / first_det.crop_path).write_bytes(b"fake crop")

    second_det = Detection(
        image_id=sample_data["images"][1].id,
        bbox_x=0.1,
        bbox_y=0.2,
        bbox_w=0.3,
        bbox_h=0.4,
        detection_confidence=0.9,
        category="animal",
        species="Dasyurus sp | Quoll sp",
        classification_confidence=0.88,
        crop_path="crops/second.jpg",
    )
    db.add(second_det)
    await db.flush()
    (tmp_path / second_det.crop_path).write_bytes(b"fake crop")

    db.add_all([
        Annotation(
            detection_id=first_det.id,
            annotator=reid_backfill.MEGAD_ANNOTATOR,
            individual_id="OLD-Q1",
        ),
        Annotation(
            detection_id=second_det.id,
            annotator=reid_backfill.MEGAD_ANNOTATOR,
            individual_id="OLD-Q2",
        ),
    ])
    await db.commit()

    stats = await reid_backfill.run_reid_backfill(db, mode="refresh_auto", limit=1)

    first_ids = (await db.execute(
        select(Annotation.individual_id).where(Annotation.detection_id == first_det.id)
    )).scalars().all()
    second_ids = (await db.execute(
        select(Annotation.individual_id).where(Annotation.detection_id == second_det.id)
    )).scalars().all()

    assert stats["candidates"] == 1
    assert stats["removed_auto"] == 1
    assert first_ids == ["NEW-Q1"]
    assert second_ids == ["OLD-Q2"]


@pytest.mark.asyncio
async def test_refresh_auto_preserves_manually_reviewed_detection(
    db: AsyncSession,
    sample_data,
    tmp_path,
    monkeypatch,
):
    await _prepare_crop_backfill(monkeypatch, tmp_path)

    det = sample_data["detections"][0]
    det.crop_path = "crops/reviewed.jpg"
    (tmp_path / det.crop_path).write_bytes(b"fake crop")
    db.add_all([
        Annotation(
            detection_id=det.id,
            annotator=reid_backfill.MEGAD_ANNOTATOR,
            individual_id="OLD-Q1",
        ),
        Annotation(
            detection_id=det.id,
            annotator="reviewer@example.com",
            is_correct=True,
        ),
    ])
    await db.commit()

    stats = await reid_backfill.run_reid_backfill(db, mode="refresh_auto", limit=1)
    rows = (await db.execute(
        select(Annotation.annotator, Annotation.individual_id)
        .where(Annotation.detection_id == det.id)
        .order_by(Annotation.annotator)
    )).all()

    assert stats["skipped"] == 1
    assert stats["removed_auto"] == 0
    assert rows == [
        (reid_backfill.MEGAD_ANNOTATOR, "OLD-Q1"),
        ("reviewer@example.com", None),
    ]
