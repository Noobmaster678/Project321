"""Tests for report generation and export endpoints."""
import pytest
from httpx import AsyncClient

from backend.app.models.annotation import Annotation
from backend.tests.conftest import auth_header

@pytest.mark.asyncio
async def test_summary_report_requires_auth(client: AsyncClient):
    resp = await client.get("/api/reports/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_summary_report_empty(client: AsyncClient, test_user):
    resp = await client.get("/api/reports/summary", headers=auth_header(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_images"] == 0


@pytest.mark.asyncio
async def test_summary_report_with_data(client: AsyncClient, sample_data, test_user):
    resp = await client.get("/api/reports/summary", headers=auth_header(test_user))
    data = resp.json()
    assert data["total_images"] == 5
    assert data["total_detections"] == 3
    assert data["total_species"] >= 1
    assert data["quoll_detections"] >= 1
    assert len(data["species_distribution"]) >= 1
    assert len(data["camera_counts"]) >= 1


@pytest.mark.asyncio
async def test_summary_report_species_filter(client: AsyncClient, sample_data, test_user):
    resp = await client.get("/api/reports/summary", params={"species": "quoll"}, headers=auth_header(test_user))
    data = resp.json()
    assert data["total_detections"] >= 1


@pytest.mark.asyncio
async def test_summary_individual_filter_deduplicates_annotations(client: AsyncClient, db, sample_data, test_user):
    det = sample_data["detections"][0]
    db.add_all([
        Annotation(detection_id=det.id, annotator="reviewer-1", individual_id="Q-01", is_correct=True),
        Annotation(detection_id=det.id, annotator="reviewer-2", individual_id="Q-01", is_correct=True),
    ])
    await db.commit()

    resp = await client.get(
        "/api/reports/summary",
        params={"individual_id": "Q-01"},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_detections"] == 1
    assert data["species_distribution"][0]["count"] == 1
    assert data["camera_counts"][0]["detections"] == 1
    assert data["hourly_activity"][0]["detections"] == 1
    assert data["monthly_activity"][0]["detections"] == 1
    assert len(data["recent_sightings"]) == 1


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, sample_data, test_user):
    resp = await client.get("/api/reports/export", params={"format": "csv"}, headers=auth_header(test_user))
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "total_images" in resp.text


@pytest.mark.asyncio
async def test_export_json(client: AsyncClient, sample_data, test_user):
    resp = await client.get("/api/reports/export", params={"format": "json"}, headers=auth_header(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_images" in data
