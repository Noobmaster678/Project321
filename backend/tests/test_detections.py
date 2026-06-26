"""Tests for detection listing, filtering, and detail endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.individual import Individual
from backend.tests.conftest import auth_header

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


@pytest.mark.asyncio
async def test_filter_by_individual_id_uses_annotation_assignments(
    client: AsyncClient,
    test_user,
    sample_data,
    db: AsyncSession,
):
    db.add(Individual(individual_id="02Q2", species="Dasyurus sp | Quoll sp"))
    await db.commit()

    det_id = sample_data["detections"][0].id
    await client.post(
        "/api/annotations/",
        json={"detection_id": det_id, "is_correct": True, "individual_id": "02Q2"},
        headers=auth_header(test_user),
    )

    resp = await client.get("/api/detections/", params={"individual_id": "02Q2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert [item["id"] for item in data["items"]] == [det_id]


@pytest.mark.asyncio
async def test_assign_individual_queue_excludes_already_assigned_quolls(
    client: AsyncClient,
    test_user,
    sample_data,
    db: AsyncSession,
):
    db.add(Individual(individual_id="02Q2", species="Dasyurus sp | Quoll sp"))
    await db.commit()

    det_id = sample_data["detections"][0].id
    await client.post(
        "/api/annotations/",
        json={"detection_id": det_id, "is_correct": True},
        headers=auth_header(test_user),
    )

    queue_resp = await client.get("/api/detections/review-queue")
    assert queue_resp.status_code == 200
    assert queue_resp.json()["assign_individual"] == 1

    await client.post(
        "/api/annotations/",
        json={"detection_id": det_id, "is_correct": True, "individual_id": "02Q2"},
        headers=auth_header(test_user),
    )

    queue_resp = await client.get("/api/detections/review-queue")
    assert queue_resp.status_code == 200
    assert queue_resp.json()["assign_individual"] == 0

    list_resp = await client.get(
        "/api/detections/",
        params={"species": "quoll", "review_status": "needs_individual"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 0
