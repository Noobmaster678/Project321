"""Tests for admin-only endpoints: user management, system metrics."""
from pathlib import Path
import sys
import types

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.config import settings
from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.services.reid_backfill import MEGAD_ANNOTATOR, run_reid_backfill
from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_list_users_admin(client: AsyncClient, admin_user, test_user):
    resp = await client.get("/api/admin/users", headers=auth_header(admin_user))
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert admin_user.email in emails
    assert test_user.email in emails


@pytest.mark.asyncio
async def test_list_users_non_admin(client: AsyncClient, test_user):
    resp = await client.get("/api/admin/users", headers=auth_header(test_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_role(client: AsyncClient, admin_user, test_user):
    resp = await client.patch(
        f"/api/admin/users/{test_user.id}/role",
        params={"role": "researcher"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "researcher"


@pytest.mark.asyncio
async def test_change_role_invalid(client: AsyncClient, admin_user, test_user):
    resp = await client.patch(
        f"/api/admin/users/{test_user.id}/role",
        params={"role": "superuser"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_system_metrics(client: AsyncClient, admin_user, sample_data):
    resp = await client.get("/api/admin/system-metrics", headers=auth_header(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_images"] == 5
    assert data["total_users"] >= 1


@pytest.mark.asyncio
async def test_reid_backfill_forbidden(client: AsyncClient, test_user):
    resp = await client.post(
        "/api/admin/reid-backfill",
        json={"mode": "missing_only", "limit": 10, "run_async": False},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reid_backfill_no_gallery(client: AsyncClient, admin_user, monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.reid_backfill.reid_gallery_path",
        lambda: Path("/__nonexistent_quoll_gallery__.pt"),
    )
    resp = await client.post(
        "/api/admin/reid-backfill",
        json={"mode": "missing_only", "limit": 10, "run_async": False},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400
    assert "gallery" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reid_backfill_refresh_auto_only_deletes_limited_candidates(db, sample_data, tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    crop_dir = storage_root / "crops"
    crop_dir.mkdir(parents=True)
    gallery = tmp_path / "gallery.pt"
    gallery.write_bytes(b"fake gallery")

    fake_pipeline = types.ModuleType("backend.worker.pipelines.megadescriptor_reid")
    fake_pipeline.predict_crop = lambda *args, **kwargs: ("Q-new", {"s1": 0.9, "gap": 0.2})
    monkeypatch.setitem(sys.modules, "backend.worker.pipelines.megadescriptor_reid", fake_pipeline)
    monkeypatch.setattr("backend.app.services.reid_backfill.reid_gallery_path", lambda: gallery)
    monkeypatch.setattr(settings, "STORAGE_ROOT", storage_root)

    dets = []
    for idx, img in enumerate(sample_data["images"][:3]):
        crop_path = f"crops/quoll-{idx}.jpg"
        (storage_root / crop_path).write_bytes(b"not a real image")
        det = Detection(
            image_id=img.id,
            bbox_x=0.1,
            bbox_y=0.1,
            bbox_w=0.2,
            bbox_h=0.2,
            detection_confidence=0.9,
            category="animal",
            species="Dasyurus sp | Quoll sp",
            classification_confidence=0.95,
            crop_path=crop_path,
        )
        db.add(det)
        await db.flush()
        db.add(Annotation(detection_id=det.id, annotator=MEGAD_ANNOTATOR, individual_id=f"Q-old-{idx}"))
        dets.append(det)
    await db.commit()

    stats = await run_reid_backfill(db, mode="refresh_auto", limit=1)

    rows = (await db.execute(
        select(Annotation.detection_id, Annotation.individual_id)
        .where(Annotation.annotator == MEGAD_ANNOTATOR)
        .order_by(Annotation.detection_id)
    )).all()
    assignments = {detection_id: individual_id for detection_id, individual_id in rows}
    assert stats["removed_auto"] == 1
    assert assignments[dets[0].id] == "Q-new"
    assert assignments[dets[1].id] == "Q-old-1"
    assert assignments[dets[2].id] == "Q-old-2"
