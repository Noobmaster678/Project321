"""Tests for dashboard statistics endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation


@pytest.mark.asyncio
async def test_dashboard_stats_empty(client: AsyncClient):
    resp = await client.get("/api/stats/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_images"] == 0
    assert data["processing_percent"] == 0.0


@pytest.mark.asyncio
async def test_dashboard_stats_with_data(client: AsyncClient, sample_data):
    resp = await client.get("/api/stats/")
    data = resp.json()
    assert data["total_images"] == 5
    assert data["processed_images"] == 5
    assert data["total_detections"] == 3
    assert data["quoll_detections"] >= 1
    assert data["total_cameras"] >= 1


@pytest.mark.asyncio
async def test_camera_stats(client: AsyncClient, sample_data):
    resp = await client.get("/api/stats/cameras")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "1A"
    assert data[0]["image_count"] == 5
    assert data[0]["latitude"] is not None


@pytest.mark.asyncio
async def test_collection_stats(client: AsyncClient, sample_data):
    resp = await client.get("/api/stats/collections")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_individual_stats_empty(client: AsyncClient):
    resp = await client.get("/api/stats/individuals")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_individual_stats_deduplicates_annotation_history(
    client: AsyncClient,
    db: AsyncSession,
    sample_data,
):
    detection = sample_data["detections"][0]
    db.add_all(
        [
            Annotation(detection_id=detection.id, individual_id="QUOLL-1"),
            Annotation(detection_id=detection.id, individual_id="QUOLL-1"),
        ]
    )
    await db.commit()

    stats_resp = await client.get("/api/stats/individuals")
    assert stats_resp.status_code == 200
    stats = next(row for row in stats_resp.json() if row["individual_id"] == "QUOLL-1")
    assert stats["total_sightings"] == 1

    timeline_resp = await client.get("/api/stats/individuals/QUOLL-1/timeline")
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert [event["detection_id"] for event in timeline["events"]] == [detection.id]
    assert timeline["monthly_counts"] == [{"month": "2023-10", "sightings": 1}]


@pytest.mark.asyncio
async def test_reid_info(client: AsyncClient):
    resp = await client.get("/api/reid/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "model_name" in data


@pytest.mark.asyncio
async def test_individual_gallery_unknown_id(client: AsyncClient):
    resp = await client.get("/api/stats/individuals/__no_such_quoll__/gallery")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["source"] == "none"
