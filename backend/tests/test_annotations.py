"""Tests for annotation CRUD (create, read, update)."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.individual import Individual
from backend.tests.conftest import auth_header


async def _seed_individual(db: AsyncSession, individual_id: str) -> None:
    db.add(Individual(individual_id=individual_id, species="Spotted-tailed Quoll"))
    await db.commit()


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
async def test_annotation_individual_assignment(client: AsyncClient, test_user, sample_data, db):
    await _seed_individual(db, "02Q2")
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
async def test_reassign_and_unassign_clears_stale_individual_ids(
    client: AsyncClient,
    test_user,
    sample_data,
    db,
):
    await _seed_individual(db, "02Q2")
    await _seed_individual(db, "03Q2")
    det_id = sample_data["detections"][0].id

    first = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "02Q2",
    }, headers=auth_header(test_user))
    assert first.status_code == 201

    second = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "03Q2",
    }, headers=auth_header(test_user))
    assert second.status_code == 201

    anns = (await client.get(f"/api/annotations/by-detection/{det_id}")).json()
    active_ids = [ann["individual_id"] for ann in anns if ann["individual_id"]]
    assert active_ids == ["03Q2"]

    resp = await client.put(
        f"/api/annotations/{second.json()['id']}",
        json={"individual_id": None},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200

    anns = (await client.get(f"/api/annotations/by-detection/{det_id}")).json()
    assert all(ann["individual_id"] is None for ann in anns)


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
