"""Tests for image listing, detail, and upload endpoints."""
import io
import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.individual import Individual
from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_list_images_empty(client: AsyncClient):
    resp = await client.get("/api/images/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_images_with_data(client: AsyncClient, sample_data):
    resp = await client.get("/api/images/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_list_images_filter_processed(client: AsyncClient, sample_data):
    resp = await client.get("/api/images/", params={"processed": True})
    data = resp.json()
    assert data["total"] == 5  # all are processed in sample_data


@pytest.mark.asyncio
async def test_list_images_filter_has_animal(client: AsyncClient, sample_data):
    resp = await client.get("/api/images/", params={"has_animal": True})
    data = resp.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_images_pagination(client: AsyncClient, sample_data):
    resp = await client.get("/api/images/", params={"per_page": 2, "page": 1})
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["pages"] == 3


@pytest.mark.asyncio
async def test_get_image_detail(client: AsyncClient, sample_data):
    img_id = sample_data["images"][0].id
    resp = await client.get(f"/api/images/{img_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "RCNX0000.JPG"
    assert data["camera"] is not None
    assert data["camera"]["name"] == "1A"


@pytest.mark.asyncio
async def test_get_image_detail_includes_detection_annotations(client: AsyncClient, test_user, sample_data, db: AsyncSession):
    det = sample_data["detections"][0]
    img_id = det.image_id
    # Seed the individual first — assignment to an unknown profile is rejected.
    db.add(Individual(individual_id="01Q1", species="Dasyurus sp | Quoll sp"))
    await db.commit()
    await client.post("/api/annotations/", json={
        "detection_id": det.id,
        "is_correct": True,
        "individual_id": "01Q1",
    }, headers=auth_header(test_user))

    resp = await client.get(f"/api/images/{img_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "detections" in data
    found = next((d for d in data["detections"] if d["id"] == det.id), None)
    assert found is not None
    assert "annotations" in found
    assert any(a.get("individual_id") == "01Q1" for a in (found["annotations"] or []))


@pytest.mark.asyncio
async def test_get_image_not_found(client: AsyncClient):
    resp = await client.get("/api/images/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_images_by_species(client: AsyncClient, sample_data):
    resp = await client.get("/api/images/by-species/quoll")
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient):
    resp = await client.post("/api/images/upload", files={"file": ("test.jpg", b"fake", "image/jpeg")})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_single(client: AsyncClient, test_user):
    fake_jpg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    resp = await client.post(
        "/api/images/upload",
        files={"file": ("test_img.jpg", fake_jpg, "image/jpeg")},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "test_img.jpg"


@pytest.mark.asyncio
async def test_upload_single_duplicate_filename_gets_suffix(client: AsyncClient, test_user):
    fake_jpg_a = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    fake_jpg_b = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x01" * 100)

    resp1 = await client.post(
        "/api/images/upload",
        files={"file": ("same_name.jpg", fake_jpg_a, "image/jpeg")},
        headers=auth_header(test_user),
    )
    resp2 = await client.post(
        "/api/images/upload",
        files={"file": ("same_name.jpg", fake_jpg_b, "image/jpeg")},
        headers=auth_header(test_user),
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["file_path"] != resp2.json()["file_path"]
    assert resp2.json()["filename"].startswith("same_name_")


@pytest.mark.asyncio
async def test_upload_bad_format(client: AsyncClient, test_user):
    resp = await client.post(
        "/api/images/upload",
        files={"file": ("test.txt", b"not an image", "text/plain")},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_batch_upload_does_not_overwrite_existing_camera_coordinates(
    client: AsyncClient, test_user, sample_data, db: AsyncSession,
):
    """Reviewers must not be able to poison shared camera GPS via batch upload."""
    from backend.app.models.camera import Camera
    from backend.app.models.deployment import Deployment

    cam = sample_data["camera"]
    coll = sample_data["collection"]
    assert cam.latitude == -35.0
    assert cam.longitude == 150.0

    dep = Deployment(
        camera_id=cam.id,
        collection_id=coll.id,
        latitude=-35.0,
        longitude=150.0,
    )
    db.add(dep)
    await db.commit()

    fake_jpg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    rel = f"{coll.name}/{cam.name}/poison.jpg"
    resp = await client.post(
        "/api/images/upload-batch",
        data={
            "relative_paths": json.dumps([rel]),
            "camera_coordinates": json.dumps({
                cam.name: {"latitude": 0.0, "longitude": 0.0},
            }),
        },
        files=[("files", ("poison.jpg", fake_jpg, "image/jpeg"))],
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200, resp.text

    await db.refresh(cam)
    assert cam.latitude == -35.0
    assert cam.longitude == 150.0

    await db.refresh(dep)
    assert dep.latitude == -35.0
    assert dep.longitude == 150.0


@pytest.mark.asyncio
async def test_batch_upload_fills_missing_camera_coordinates(
    client: AsyncClient, test_user, db: AsyncSession,
):
    """New/incomplete cameras may still receive GPS on first batch upload."""
    from backend.app.models.camera import Camera

    cam = Camera(name="9Z", camera_number=9, side="Z", latitude=None, longitude=None)
    db.add(cam)
    await db.commit()

    fake_jpg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    rel = "NewCollection/9Z/first.jpg"
    resp = await client.post(
        "/api/images/upload-batch",
        data={
            "relative_paths": json.dumps([rel]),
            "camera_coordinates": json.dumps({
                "9Z": {"latitude": -34.5, "longitude": 149.25},
            }),
        },
        files=[("files", ("first.jpg", fake_jpg, "image/jpeg"))],
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200, resp.text

    await db.refresh(cam)
    assert cam.latitude == -34.5
    assert cam.longitude == 149.25
