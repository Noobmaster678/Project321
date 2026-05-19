"""Tests for admin-only endpoints: user management, system metrics."""
import sys
import types
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.annotation import Annotation
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
async def test_reid_backfill_refresh_auto_respects_limit(
    db: AsyncSession,
    sample_data,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "STORAGE_ROOT", tmp_path)
    crops_dir = tmp_path / "crops"
    crops_dir.mkdir()

    gallery = tmp_path / "models" / "gallery.pt"
    gallery.parent.mkdir()
    gallery.write_bytes(b"fake gallery")
    monkeypatch.setattr("backend.app.services.reid_backfill.reid_gallery_path", lambda: gallery)

    dummy_reid = types.ModuleType("backend.worker.pipelines.megadescriptor_reid")
    dummy_reid.predict_crop = lambda *_args, **_kwargs: (
        "new-quoll",
        {"s1": 0.91, "gap": 0.22},
    )
    monkeypatch.setitem(sys.modules, "backend.worker.pipelines.megadescriptor_reid", dummy_reid)

    detections = sample_data["detections"]
    for det in detections:
        det.species = "Dasyurus sp | Quoll sp"
        det.crop_path = f"crops/{det.id}.jpg"
        (tmp_path / det.crop_path).write_bytes(b"crop")
        db.add(
            Annotation(
                detection_id=det.id,
                annotator=MEGAD_ANNOTATOR,
                individual_id=f"old-{det.id}",
            )
        )
    await db.commit()

    stats = await run_reid_backfill(db, mode="refresh_auto", limit=1)

    rows = (await db.execute(select(Annotation).order_by(Annotation.detection_id))).scalars().all()
    annotations_by_detection: dict[int, list[Annotation]] = {}
    for ann in rows:
        annotations_by_detection.setdefault(ann.detection_id, []).append(ann)

    assert stats["removed_auto"] == 1
    assert any(
        ann.individual_id == "new-quoll"
        for ann in annotations_by_detection[detections[0].id]
    )
    for det in detections[1:]:
        assert [ann.individual_id for ann in annotations_by_detection[det.id]] == [f"old-{det.id}"]
