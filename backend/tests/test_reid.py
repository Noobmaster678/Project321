"""Tests for re-ID suggestion endpoint access control."""
import sys
import types

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api import reid
from backend.app.models.reid_suggestion_feedback import ReidSuggestionFeedback
from backend.tests.conftest import auth_header


async def _prepare_reid_detection(db: AsyncSession, sample_data, tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    crop_dir = storage_root / "crops"
    crop_dir.mkdir(parents=True)
    crop = crop_dir / "det-1.jpg"
    crop.write_bytes(b"fake crop")

    gallery = storage_root / "models" / "gallery.pt"
    gallery.parent.mkdir(parents=True)
    gallery.write_bytes(b"fake gallery")

    det = sample_data["detections"][0]
    det.crop_path = "crops/det-1.jpg"
    await db.commit()

    monkeypatch.setattr(reid.settings, "STORAGE_ROOT", storage_root)
    monkeypatch.setattr(reid, "reid_gallery_path", lambda: gallery)
    return det.id


@pytest.mark.asyncio
async def test_reid_suggestions_require_auth(client: AsyncClient, db: AsyncSession, sample_data, tmp_path, monkeypatch):
    det_id = await _prepare_reid_detection(db, sample_data, tmp_path, monkeypatch)
    called = False

    def fake_predict_topk_crop(*_args, **_kwargs):
        nonlocal called
        called = True
        return {"suggestions": []}

    fake_module = types.SimpleNamespace(predict_topk_crop=fake_predict_topk_crop)
    monkeypatch.setitem(sys.modules, "backend.worker.pipelines.megadescriptor_reid", fake_module)

    resp = await client.get(f"/api/reid/detections/{det_id}/suggestions")

    assert resp.status_code == 401
    assert called is False


@pytest.mark.asyncio
async def test_reid_suggestions_with_auth_logs_suggestions(
    client: AsyncClient,
    db: AsyncSession,
    test_user,
    sample_data,
    tmp_path,
    monkeypatch,
):
    det_id = await _prepare_reid_detection(db, sample_data, tmp_path, monkeypatch)

    def fake_predict_topk_crop(*_args, **_kwargs):
        return {
            "suggestions": [
                {
                    "rank": 1,
                    "individual_id": "02Q2",
                    "similarity": 0.91,
                    "confidence": 0.88,
                    "accepted_by_gate": True,
                }
            ],
            "sim_threshold": 0.35,
            "gap_threshold": 0.05,
            "gap": 0.2,
        }

    fake_module = types.SimpleNamespace(predict_topk_crop=fake_predict_topk_crop)
    monkeypatch.setitem(sys.modules, "backend.worker.pipelines.megadescriptor_reid", fake_module)

    resp = await client.get(
        f"/api/reid/detections/{det_id}/suggestions",
        headers=auth_header(test_user),
    )

    assert resp.status_code == 200
    assert resp.json()["suggestions"][0]["individual_id"] == "02Q2"

    rows = (
        await db.execute(
            select(ReidSuggestionFeedback).where(ReidSuggestionFeedback.detection_id == det_id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].suggested_individual_id == "02Q2"
