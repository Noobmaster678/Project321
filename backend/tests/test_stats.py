"""Tests for dashboard statistics endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.models.individual import Individual
from backend.app.models.sighting import Sighting


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


@pytest.mark.asyncio
async def test_gallery_uses_image_detections_when_csv_sighting_has_no_detection_id(
    client: AsyncClient, sample_data, db: AsyncSession,
):
    """CSV import leaves Sighting.detection_id NULL; crops live on Detection."""
    ind = Individual(individual_id="01Q1", species="Spotted-tailed Quoll", total_sightings=1)
    db.add(ind)
    await db.flush()

    img = sample_data["images"][0]
    det = sample_data["detections"][0]
    det.crop_path = "crops/1/0_0.jpg"
    db.add(Sighting(individual_id=ind.id, image_id=img.id, source="csv_import"))
    await db.commit()

    resp = await client.get("/api/stats/individuals/01Q1/gallery")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "sightings"
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["image_id"] == img.id
    assert item["detection_id"] == det.id
    assert item["crop_url"] == "/storage/crops/1/0_0.jpg"
    assert item["display_url"] == "/storage/crops/1/0_0.jpg"


@pytest.mark.asyncio
async def test_gallery_merges_review_assignments_with_csv_sightings(
    client: AsyncClient, sample_data, db: AsyncSession,
):
    """A CSV sighting must not hide later review-assigned crops on other images."""
    ind = Individual(individual_id="02Q1", species="Spotted-tailed Quoll", total_sightings=1)
    db.add(ind)
    await db.flush()

    csv_img = sample_data["images"][0]
    csv_det = sample_data["detections"][0]
    csv_det.crop_path = "crops/1/csv.jpg"
    db.add(Sighting(individual_id=ind.id, image_id=csv_img.id, source="csv_import"))

    review_img = sample_data["images"][1]
    review_det = Detection(
        image_id=review_img.id,
        bbox_x=0.1, bbox_y=0.1, bbox_w=0.4, bbox_h=0.4,
        detection_confidence=0.9,
        category="animal",
        species="Dasyurus sp | Quoll sp",
        classification_confidence=0.88,
        crop_path="crops/1/review.jpg",
    )
    db.add(review_det)
    await db.flush()
    db.add(Annotation(
        detection_id=review_det.id,
        annotator="reviewer@example.com",
        individual_id="02Q1",
        is_correct=True,
    ))
    await db.commit()

    resp = await client.get("/api/stats/individuals/02Q1/gallery")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "merged"
    urls = {item["display_url"] for item in data["items"]}
    assert "/storage/crops/1/csv.jpg" in urls
    assert "/storage/crops/1/review.jpg" in urls
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_gallery_falls_back_to_file_path_when_no_thumb_or_crop(
    client: AsyncClient, sample_data, db: AsyncSession,
):
    """Unprocessed CSV sightings should still render the original image path."""
    ind = Individual(individual_id="03Q1", species="Spotted-tailed Quoll", total_sightings=1)
    db.add(ind)
    await db.flush()
    img = sample_data["images"][3]
    db.add(Sighting(individual_id=ind.id, image_id=img.id, source="csv_import"))
    await db.commit()

    resp = await client.get("/api/stats/individuals/03Q1/gallery")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["display_url"] == "/storage/" + img.file_path.replace("\\", "/")
    assert data["items"][0]["detection_id"] is None


@pytest.mark.asyncio
async def test_gallery_still_uses_annotations_when_no_sightings(
    client: AsyncClient, sample_data, db: AsyncSession,
):
    """Review-only IDs (no CSV sighting / no individuals row) must still populate."""
    det = sample_data["detections"][0]
    det.crop_path = "crops/1/ann_only.jpg"
    db.add(Annotation(
        detection_id=det.id,
        annotator="reviewer@example.com",
        individual_id="99Q1",
        is_correct=True,
    ))
    await db.commit()

    resp = await client.get("/api/stats/individuals/99Q1/gallery")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "annotations"
    assert len(data["items"]) == 1
    assert data["items"][0]["display_url"] == "/storage/crops/1/ann_only.jpg"
