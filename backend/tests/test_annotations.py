"""Tests for annotation CRUD (create, read, update)."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.individual import Individual
from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_create_annotation(client: AsyncClient, test_user, sample_data):
    det_id = sample_data["detections"][0].id
    resp = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "notes": "Looks like a quoll",
    }, headers=auth_header(test_user))
    assert resp.status_code == 201
    data = resp.json()
    assert data["detection_id"] == det_id
    assert data["is_correct"] is True
    assert data["annotator"] == test_user.email


@pytest.mark.asyncio
async def test_create_annotation_missing_detection(client: AsyncClient, test_user):
    resp = await client.post("/api/annotations/", json={
        "detection_id": 9999, "is_correct": False,
    }, headers=auth_header(test_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_annotation_requires_auth(client: AsyncClient, sample_data):
    det_id = sample_data["detections"][0].id
    resp = await client.post("/api/annotations/", json={"detection_id": det_id, "is_correct": True})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_annotations_for_detection(client: AsyncClient, test_user, sample_data):
    det_id = sample_data["detections"][0].id
    await client.post("/api/annotations/", json={
        "detection_id": det_id, "is_correct": True,
    }, headers=auth_header(test_user))

    resp = await client.get(f"/api/annotations/by-detection/{det_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_update_annotation(client: AsyncClient, test_user, sample_data):
    det_id = sample_data["detections"][0].id
    create_resp = await client.post("/api/annotations/", json={
        "detection_id": det_id, "is_correct": True,
    }, headers=auth_header(test_user))
    ann_id = create_resp.json()["id"]

    resp = await client.put(f"/api/annotations/{ann_id}", json={
        "is_correct": False,
        "corrected_species": "Trichosurus sp | Brushtail Possum sp",
        "notes": "Actually a possum",
    }, headers=auth_header(test_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is False
    assert data["corrected_species"] == "Trichosurus sp | Brushtail Possum sp"


@pytest.mark.asyncio
async def test_annotation_individual_assignment(client: AsyncClient, test_user, sample_data, db: AsyncSession):
    # The profile must exist before a detection can be assigned to it; the API
    # rejects assignment to an unknown individual to protect data integrity.
    db.add(Individual(individual_id="02Q2", species="Dasyurus sp | Quoll sp"))
    await db.commit()

    det_id = sample_data["detections"][0].id
    resp = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "02Q2",
    }, headers=auth_header(test_user))
    assert resp.status_code == 201
    data = resp.json()
    assert data["individual_id"] == "02Q2"


@pytest.mark.asyncio
async def test_individual_assignment_replaces_stale_assignment(client: AsyncClient, test_user, sample_data, db: AsyncSession):
    db.add_all([
        Individual(individual_id="02Q2", species="Dasyurus sp | Quoll sp"),
        Individual(individual_id="03Q3", species="Dasyurus sp | Quoll sp"),
    ])
    await db.commit()

    det_id = sample_data["detections"][0].id
    first_resp = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "02Q2",
    }, headers=auth_header(test_user))
    assert first_resp.status_code == 201

    second_resp = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "03Q3",
    }, headers=auth_header(test_user))
    assert second_resp.status_code == 201

    resp = await client.get(f"/api/annotations/by-detection/{det_id}")
    active_ids = [a["individual_id"] for a in resp.json() if a["individual_id"]]
    assert active_ids == ["03Q3"]


@pytest.mark.asyncio
async def test_unassign_clears_all_stale_individual_assignments(client: AsyncClient, test_user, sample_data, db: AsyncSession):
    db.add_all([
        Individual(individual_id="02Q2", species="Dasyurus sp | Quoll sp"),
        Individual(individual_id="03Q3", species="Dasyurus sp | Quoll sp"),
    ])
    await db.commit()

    det_id = sample_data["detections"][0].id
    await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "02Q2",
    }, headers=auth_header(test_user))
    create_resp = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "03Q3",
    }, headers=auth_header(test_user))
    ann_id = create_resp.json()["id"]

    unassign_resp = await client.put(
        f"/api/annotations/{ann_id}",
        json={"individual_id": None},
        headers=auth_header(test_user),
    )
    assert unassign_resp.status_code == 200

    resp = await client.get(f"/api/annotations/by-detection/{det_id}")
    active_ids = [a["individual_id"] for a in resp.json() if a["individual_id"]]
    assert active_ids == []


@pytest.mark.asyncio
async def test_annotation_unknown_individual_rejected(client: AsyncClient, test_user, sample_data):
    """Assigning a detection to a non-existent profile returns 404."""
    det_id = sample_data["detections"][0].id
    resp = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "NOPE-999",
    }, headers=auth_header(test_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_annotation_flag_retraining(client: AsyncClient, test_user, sample_data):
    det_id = sample_data["detections"][1].id
    resp = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": False,
        "corrected_species": "Felis catus | Domestic Cat",
        "flag_for_retraining": True,
    }, headers=auth_header(test_user))
    assert resp.status_code == 201
