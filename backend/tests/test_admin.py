"""Tests for admin-only endpoints: user management, system metrics."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.tests.conftest import auth_header
from backend.app.config import settings
from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.models.image import Image
from backend.app.services.reid_backfill import MEGAD_ANNOTATOR, run_reid_backfill


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
async def test_refresh_auto_only_removes_annotations_within_limit(db, tmp_path, monkeypatch):
    """Refreshing a limited batch must not delete auto IDs outside that batch."""
    gallery = tmp_path / "gallery.pt"
    gallery.write_bytes(b"test gallery")
    monkeypatch.setattr(
        "backend.app.services.reid_backfill.reid_gallery_path",
        lambda: gallery,
    )
    monkeypatch.setattr(settings, "STORAGE_ROOT", tmp_path)
    monkeypatch.setitem(
        sys.modules,
        "backend.worker.pipelines.megadescriptor_reid",
        SimpleNamespace(predict_crop=lambda *args, **kwargs: ("new-iid", {"s1": 0.9, "gap": 0.2})),
    )

    detections = []
    for idx in range(3):
        crop_path = Path("crops") / f"quoll-{idx}.jpg"
        (tmp_path / crop_path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / crop_path).write_bytes(b"crop")
        img = Image(filename=f"quoll-{idx}.jpg", file_path=f"uploads/quoll-{idx}.jpg")
        db.add(img)
        await db.flush()
        det = Detection(
            image_id=img.id,
            bbox_x=0.1,
            bbox_y=0.2,
            bbox_w=0.3,
            bbox_h=0.4,
            detection_confidence=0.95,
            category="animal",
            species="Dasyurus sp | Quoll sp",
            classification_confidence=0.9,
            crop_path=str(crop_path),
        )
        db.add(det)
        await db.flush()
        db.add(
            Annotation(
                detection_id=det.id,
                annotator=MEGAD_ANNOTATOR,
                individual_id=f"old-iid-{idx}",
            )
        )
        detections.append(det)
    await db.commit()

    stats = await run_reid_backfill(db, mode="refresh_auto", limit=1)
    await db.commit()

    assert stats["removed_auto"] == 1
    assert stats["assigned"] == 1

    rows = (
        await db.execute(
            select(Annotation.detection_id, Annotation.individual_id)
            .where(Annotation.annotator == MEGAD_ANNOTATOR)
            .order_by(Annotation.detection_id, Annotation.id)
        )
    ).all()
    annotations_by_detection = {}
    for detection_id, individual_id in rows:
        annotations_by_detection.setdefault(detection_id, []).append(individual_id)

    assert annotations_by_detection[detections[0].id] == ["new-iid"]
    assert annotations_by_detection[detections[1].id] == ["old-iid-1"]
    assert annotations_by_detection[detections[2].id] == ["old-iid-2"]
