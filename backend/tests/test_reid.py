"""Tests for re-identification endpoints and backfill safety."""
import sys
import types

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.models.annotation import Annotation
from backend.app.services import reid_backfill
from backend.app.services.reid_backfill import MEGAD_ANNOTATOR, run_reid_backfill


@pytest.mark.asyncio
async def test_reid_suggestions_require_auth(client: AsyncClient, sample_data):
    det_id = sample_data["detections"][0].id

    resp = await client.get(f"/api/reid/detections/{det_id}/suggestions")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_auto_only_deletes_limited_candidates(db, sample_data, tmp_path, monkeypatch):
    crop_dir = tmp_path / "crops"
    crop_dir.mkdir()
    for det in sample_data["detections"]:
        det.species = "Dasyurus sp | Quoll sp"
        det.crop_path = f"crops/{det.id}.jpg"
        (tmp_path / det.crop_path).write_bytes(b"fake crop")
        db.add(
            Annotation(
                detection_id=det.id,
                annotator=MEGAD_ANNOTATOR,
                individual_id=f"old-{det.id}",
            )
        )
    await db.commit()

    gallery = tmp_path / "gallery.pt"
    gallery.write_bytes(b"fake gallery")
    monkeypatch.setattr(reid_backfill, "reid_gallery_path", lambda: gallery)
    monkeypatch.setattr(reid_backfill.settings, "STORAGE_ROOT", tmp_path)

    fake_module = types.ModuleType("backend.worker.pipelines.megadescriptor_reid")
    fake_module.predict_crop = lambda *args, **kwargs: ("new-id", {"s1": 0.9, "gap": 0.2})
    monkeypatch.setitem(sys.modules, "backend.worker.pipelines.megadescriptor_reid", fake_module)

    stats = await run_reid_backfill(db, mode="refresh_auto", limit=1)

    rows = (
        await db.execute(select(Annotation).order_by(Annotation.detection_id, Annotation.id))
    ).scalars().all()
    ids_by_detection: dict[int, list[str | None]] = {}
    for row in rows:
        ids_by_detection.setdefault(row.detection_id, []).append(row.individual_id)

    first_id = sample_data["detections"][0].id
    untouched_ids = [det.id for det in sample_data["detections"][1:]]
    assert stats["removed_auto"] == 1
    assert ids_by_detection[first_id] == ["new-id"]
    for det_id in untouched_ids:
        assert ids_by_detection[det_id] == [f"old-{det_id}"]
