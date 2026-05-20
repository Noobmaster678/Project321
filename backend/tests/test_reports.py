"""Tests for report generation and export endpoints."""
import pytest
from httpx import AsyncClient

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


@pytest.mark.asyncio
async def test_summary_report_individual_filter_deduplicates(client: AsyncClient, test_user, sample_data):
    det_id = sample_data["detections"][0].id
    for _ in range(2):
        await client.post(
            "/api/annotations/",
            json={"detection_id": det_id, "individual_id": "02Q2"},
            headers=auth_header(test_user),
        )

    resp = await client.get("/api/reports/summary", params={"individual_id": "02Q2"})
    data = resp.json()
    assert data["total_detections"] == 1
    assert data["species_distribution"][0]["count"] == 1
    assert data["camera_counts"][0]["detections"] == 1


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, sample_data, test_user):
    resp = await client.get(
        "/api/reports/export",
        params={"format": "csv"},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "total_images" in resp.text


@pytest.mark.asyncio
async def test_export_json(client: AsyncClient, sample_data, test_user):
    resp = await client.get(
        "/api/reports/export",
        params={"format": "json"},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_images" in data
