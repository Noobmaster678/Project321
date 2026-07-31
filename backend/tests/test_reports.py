"""Tests for report generation and export endpoints."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation
from backend.app.models.camera import Camera
from backend.app.models.collection import Collection
from backend.app.models.deployment import Deployment
from backend.app.models.detection import Detection
from backend.app.models.image import Image
from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_summary_report_empty(client: AsyncClient):
    resp = await client.get("/api/reports/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_images"] == 0


@pytest.mark.asyncio
async def test_summary_report_with_data(client: AsyncClient, sample_data):
    resp = await client.get("/api/reports/summary")
    data = resp.json()
    assert data["total_images"] == 5
    assert data["total_detections"] == 3
    assert data["total_species"] >= 1
    assert data["quoll_detections"] >= 1
    assert len(data["species_distribution"]) >= 1
    assert len(data["camera_counts"]) >= 1


@pytest.mark.asyncio
async def test_summary_report_species_filter(client: AsyncClient, sample_data):
    resp = await client.get("/api/reports/summary", params={"species": "quoll"})
    data = resp.json()
    assert data["total_detections"] >= 1


# Report exports are gated behind authentication (consistent with the
# /api/exports/* endpoints), so these requests carry an auth header.

@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, test_user, sample_data):
    resp = await client.get("/api/reports/export", params={"format": "csv"}, headers=auth_header(test_user))
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "total_images" in resp.text


@pytest.mark.asyncio
async def test_export_json(client: AsyncClient, test_user, sample_data):
    resp = await client.get("/api/reports/export", params={"format": "json"}, headers=auth_header(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_images" in data


@pytest.mark.asyncio
async def test_export_requires_auth(client: AsyncClient, sample_data):
    """Exporting report data requires a logged-in user."""
    resp = await client.get("/api/reports/export", params={"format": "csv"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_filtered_rai_uses_scoped_trap_nights(client: AsyncClient, db: AsyncSession):
    """Camera-filtered RAI must not dilute events by out-of-scope trap-nights.

    Concrete trigger: two cameras with stored deployments (10 vs 990 trap-nights).
    CAM-A has one independent quoll event. Filtering to CAM-A must use ~10 nights
    (RAI ≈ 10), not the global 1000 nights (RAI ≈ 0.1).
    """
    cam_a = Camera(name="CAM-A", latitude=-35.0, longitude=150.0)
    cam_b = Camera(name="CAM-B", latitude=-35.1, longitude=150.1)
    db.add_all([cam_a, cam_b])
    await db.flush()

    coll = Collection(name="RAI-Coll", collection_number=99)
    db.add(coll)
    await db.flush()

    db.add_all([
        Deployment(camera_id=cam_a.id, collection_id=coll.id, trap_nights=10.0),
        Deployment(camera_id=cam_b.id, collection_id=coll.id, trap_nights=990.0),
    ])

    img_a1 = Image(
        filename="a1.JPG",
        file_path="uploads/a1.JPG",
        camera_id=cam_a.id,
        collection_id=coll.id,
        processed=True,
        has_animal=True,
        captured_at=datetime(2023, 10, 1, 8, 0, tzinfo=timezone.utc),
        event_id=1,
    )
    img_a2 = Image(
        filename="a2.JPG",
        file_path="uploads/a2.JPG",
        camera_id=cam_a.id,
        collection_id=coll.id,
        processed=True,
        has_animal=True,
        captured_at=datetime(2023, 10, 11, 8, 0, tzinfo=timezone.utc),
        event_id=1,
    )
    img_b = Image(
        filename="b1.JPG",
        file_path="uploads/b1.JPG",
        camera_id=cam_b.id,
        collection_id=coll.id,
        processed=True,
        has_animal=True,
        captured_at=datetime(2023, 10, 5, 8, 0, tzinfo=timezone.utc),
        event_id=2,
    )
    db.add_all([img_a1, img_a2, img_b])
    await db.flush()

    db.add_all([
        Detection(
            image_id=img_a1.id,
            bbox_x=0.1, bbox_y=0.1, bbox_w=0.2, bbox_h=0.2,
            detection_confidence=0.9, category="animal",
            species="Dasyurus sp | Quoll sp", classification_confidence=0.9,
        ),
        Detection(
            image_id=img_b.id,
            bbox_x=0.1, bbox_y=0.1, bbox_w=0.2, bbox_h=0.2,
            detection_confidence=0.9, category="animal",
            species="Dasyurus sp | Quoll sp", classification_confidence=0.9,
        ),
    ])
    await db.commit()

    unfiltered = (await client.get("/api/reports/summary")).json()
    assert unfiltered["total_trap_nights"] == 1000.0

    filtered = (
        await client.get("/api/reports/summary", params={"camera_name": "CAM-A"})
    ).json()
    # Image span on CAM-A is 10 days → scoped trap-nights = 10
    assert filtered["total_trap_nights"] == 10.0
    assert filtered["total_trap_nights"] != unfiltered["total_trap_nights"]

    quoll_rai = next(e for e in filtered["rai_data"] if "quoll" in e["species"].lower())
    assert quoll_rai["independent_events"] == 1
    assert quoll_rai["total_trap_nights"] == 10.0
    assert quoll_rai["rai"] == pytest.approx(10.0, rel=1e-3)


@pytest.mark.asyncio
async def test_individual_filter_does_not_inflate_detection_counts(
    client: AsyncClient, db: AsyncSession, sample_data,
):
    """Duplicate assignment-history rows for one detection must not inflate filtered counts."""
    det = sample_data["detections"][0]
    db.add_all([
        Annotation(detection_id=det.id, annotator="reviewer@example.com", individual_id="02Q2", is_correct=True),
        Annotation(detection_id=det.id, annotator="reviewer@example.com", individual_id="02Q2", is_correct=True),
    ])
    await db.commit()

    resp = await client.get("/api/reports/summary", params={"individual_id": "02Q2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_detections"] == 1
    assert sum(s["count"] for s in data["species_distribution"]) == 1
