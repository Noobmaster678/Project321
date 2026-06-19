"""Tests for detection listing, filtering, and detail endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection


@pytest.mark.asyncio
async def test_list_detections_empty(client: AsyncClient):
    resp = await client.get("/api/detections/")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_detections_with_data(client: AsyncClient, sample_data):
    resp = await client.get("/api/detections/")
    data = resp.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_filter_by_species(client: AsyncClient, sample_data):
    resp = await client.get("/api/detections/", params={"species": "quoll"})
    data = resp.json()
    assert data["total"] == 1
    assert "quoll" in data["items"][0]["species"].lower()


@pytest.mark.asyncio
async def test_filter_by_min_confidence(client: AsyncClient, sample_data):
    resp = await client.get("/api/detections/", params={"min_confidence": 0.8})
    data = resp.json()
    assert all(d["classification_confidence"] >= 0.8 for d in data["items"])


@pytest.mark.asyncio
async def test_filter_by_individual_id(client: AsyncClient, sample_data, db: AsyncSession):
    target_det = sample_data["detections"][0]
    other_det = sample_data["detections"][1]
    db.add_all([
        Annotation(detection_id=target_det.id, individual_id="02Q2"),
        Annotation(detection_id=other_det.id, individual_id="03Q3"),
    ])
    await db.commit()

    resp = await client.get("/api/detections/", params={"individual_id": "02Q2"})
    data = resp.json()

    assert data["total"] == 1
    assert data["items"][0]["id"] == target_det.id


@pytest.mark.asyncio
async def test_review_queue_assign_individual_excludes_already_assigned(
    client: AsyncClient,
    sample_data,
    db: AsyncSession,
):
    assigned_det = sample_data["detections"][0]
    unassigned_det = Detection(
        image_id=sample_data["images"][1].id,
        bbox_x=0.1,
        bbox_y=0.2,
        bbox_w=0.3,
        bbox_h=0.4,
        detection_confidence=0.9,
        category="animal",
        species="Dasyurus sp | Quoll sp",
        classification_confidence=0.88,
    )
    db.add(unassigned_det)
    await db.flush()
    db.add_all([
        Annotation(detection_id=assigned_det.id, is_correct=True),
        Annotation(detection_id=assigned_det.id, individual_id="02Q2"),
        Annotation(detection_id=unassigned_det.id, is_correct=True),
    ])
    await db.commit()

    resp = await client.get("/api/detections/review-queue")
    data = resp.json()

    assert data["assign_individual"] == 1


@pytest.mark.asyncio
async def test_species_counts(client: AsyncClient, sample_data):
    resp = await client.get("/api/detections/species-counts")
    assert resp.status_code == 200
    counts = resp.json()
    assert len(counts) >= 1
    species_names = [c["species"] for c in counts]
    assert any("Wallaby" in s for s in species_names)


@pytest.mark.asyncio
async def test_get_detection_detail(client: AsyncClient, sample_data):
    det_id = sample_data["detections"][0].id
    resp = await client.get(f"/api/detections/{det_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["image"] is not None
    assert data["annotations"] == []


@pytest.mark.asyncio
async def test_get_detection_not_found(client: AsyncClient):
    resp = await client.get("/api/detections/9999")
    assert resp.status_code == 404
