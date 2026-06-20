"""Tests for annotation CRUD (create, read, update)."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation
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
async def test_reassigning_individual_clears_previous_assignment(
    client: AsyncClient,
    test_user,
    sample_data,
    db: AsyncSession,
):
    db.add_all([
        Individual(individual_id="02Q2", species="Dasyurus sp | Quoll sp"),
        Individual(individual_id="03Q1", species="Dasyurus sp | Quoll sp"),
    ])
    await db.commit()

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
        "individual_id": "03Q1",
    }, headers=auth_header(test_user))
    assert second.status_code == 201

    old_gallery = await client.get("/api/stats/individuals/02Q2/gallery")
    assert old_gallery.status_code == 200
    assert old_gallery.json()["items"] == []

    new_gallery = await client.get("/api/stats/individuals/03Q1/gallery")
    assert new_gallery.status_code == 200
    assert [item["detection_id"] for item in new_gallery.json()["items"]] == [det_id]

    old_ann = await db.get(Annotation, first.json()["id"])
    new_ann = await db.get(Annotation, second.json()["id"])
    assert old_ann is not None
    assert new_ann is not None
    assert old_ann.individual_id is None
    assert new_ann.individual_id == "03Q1"


@pytest.mark.asyncio
async def test_unassigning_individual_clears_stale_assignments(
    client: AsyncClient,
    test_user,
    sample_data,
    db: AsyncSession,
):
    db.add_all([
        Individual(individual_id="02Q2", species="Dasyurus sp | Quoll sp"),
        Individual(individual_id="03Q1", species="Dasyurus sp | Quoll sp"),
    ])
    await db.commit()

    det_id = sample_data["detections"][0].id
    await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "02Q2",
    }, headers=auth_header(test_user))
    current = await client.post("/api/annotations/", json={
        "detection_id": det_id,
        "is_correct": True,
        "individual_id": "03Q1",
    }, headers=auth_header(test_user))
    assert current.status_code == 201

    unassign = await client.put(
        f"/api/annotations/{current.json()['id']}",
        json={"individual_id": None},
        headers=auth_header(test_user),
    )
    assert unassign.status_code == 200

    annotations = (await client.get(f"/api/annotations/by-detection/{det_id}")).json()
    assert all(a["individual_id"] is None for a in annotations)


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
