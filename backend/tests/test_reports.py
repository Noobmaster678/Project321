"""Tests for report generation and export endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.individual import Individual
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


async def _assign_individuals(client: AsyncClient, test_user, db: AsyncSession, sample_data) -> tuple[int, int]:
    """Assign 02Q1 and 02Q10 to two quoll detections (02Q1 is a substring of 02Q10)."""
    dets = sample_data["detections"]
    dets[1].species = "Dasyurus sp | Quoll sp"
    db.add(Individual(individual_id="02Q1", species="Dasyurus sp | Quoll sp"))
    db.add(Individual(individual_id="02Q10", species="Dasyurus sp | Quoll sp"))
    await db.commit()

    for det_id, iid in ((dets[0].id, "02Q1"), (dets[1].id, "02Q10")):
        resp = await client.post(
            "/api/annotations/",
            json={"detection_id": det_id, "is_correct": True, "individual_id": iid},
            headers=auth_header(test_user),
        )
        assert resp.status_code == 201, resp.text
    return dets[0].id, dets[1].id


@pytest.mark.asyncio
async def test_individual_filter_is_exact_not_substring(
    client: AsyncClient, test_user, sample_data, db: AsyncSession
):
    """Filtering by 02Q1 must not pull in 02Q10 (wildcard ILIKE would)."""
    q1_id, q10_id = await _assign_individuals(client, test_user, db, sample_data)

    summary = await client.get("/api/reports/summary", params={"individual_id": "02Q1"})
    assert summary.status_code == 200
    assert summary.json()["total_detections"] == 1

    exported = await client.get(
        "/api/reports/export",
        params={"format": "json", "individual_id": "02Q1"},
        headers=auth_header(test_user),
    )
    assert exported.status_code == 200
    assert exported.json()["total_detections"] == 1

    metadata = await client.get(
        "/api/exports/metadata",
        params={"individual_id": "02Q1", "format": "json"},
        headers=auth_header(test_user),
    )
    assert metadata.status_code == 200
    meta_ids = [row["detection_id"] for row in metadata.json()]
    assert meta_ids == [q1_id]
    assert q10_id not in meta_ids

    quolls = await client.get(
        "/api/exports/quoll-detections",
        params={"individual_id": "02Q1", "format": "json"},
        headers=auth_header(test_user),
    )
    assert quolls.status_code == 200
    quoll_ids = [row["detection_id"] for row in quolls.json()]
    assert quoll_ids == [q1_id]
    assert q10_id not in quoll_ids
