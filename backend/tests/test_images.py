"""Tests for image listing, detail, and upload endpoints."""
import io
import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.images import UPLOAD_DIR
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
        files={"file": ("unique_single_upload.jpg", fake_jpg, "image/jpeg")},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "unique_single_upload.jpg"
    saved = UPLOAD_DIR / "unique_single_upload.jpg"
    if saved.exists():
        saved.unlink()


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
async def test_upload_batch_rejects_relative_path_extension_mismatch(client: AsyncClient, test_user):
    """relative_paths must not save non-image files behind a .jpg UploadFile name.

    Trigger: authenticated batch upload with files[0].filename="safe.jpg" but
    relative_paths=["payload.html"]. Before the fix the allowlist checked only
    UploadFile.filename while the saved path used relative_paths, writing HTML
    under /storage for same-origin XSS.
    """
    fake_jpg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    resp = await client.post(
        "/api/images/upload-batch",
        files=[("files", ("safe.jpg", fake_jpg, "image/jpeg"))],
        data={"relative_paths": json.dumps(["payload.html"])},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["files_received"] == 0
    assert not (UPLOAD_DIR / "payload.html").exists()


@pytest.mark.asyncio
async def test_upload_skips_filesystem_collision_without_overwriting(client: AsyncClient, test_user):
    """If the target path already exists on disk, reserve the next suffix.

    Trigger: an orphaned file occupies uploads/orphan.jpg with no DB row. A new
    upload of orphan.jpg must not open that path with 'wb' and destroy the
    existing bytes (and under concurrency, another request's surviving row).
    """
    orphan = UPLOAD_DIR / "orphan.jpg"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"ORIGINAL-BYTES-DO-NOT-CLOBBER")
    saved = None
    try:
        fake_jpg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        resp = await client.post(
            "/api/images/upload",
            files={"file": ("orphan.jpg", fake_jpg, "image/jpeg")},
            headers=auth_header(test_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_path"] != "uploads/orphan.jpg"
        assert data["filename"].startswith("orphan_")
        assert orphan.read_bytes() == b"ORIGINAL-BYTES-DO-NOT-CLOBBER"
        saved = Path(UPLOAD_DIR.parent) / data["file_path"]
        assert saved.exists()
    finally:
        if orphan.exists():
            orphan.unlink()
        if saved is not None and saved.exists():
            saved.unlink()
        # Clean any other orphan_N leftovers from prior runs.
        for leftover in UPLOAD_DIR.glob("orphan_*.jpg"):
            leftover.unlink()

