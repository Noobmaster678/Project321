"""Regression: auto re-ID annotations must not evacuate the verify queue."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation


@pytest.mark.asyncio
async def test_auto_reid_annotation_keeps_quoll_in_verify_queue(
    client: AsyncClient, sample_data, db: AsyncSession
):
    quoll = sample_data["detections"][0]
    assert "quoll" in (quoll.species or "").lower()

    before = await client.get("/api/detections/review-queue")
    assert before.status_code == 200
    before_verify = before.json()["verify_quolls"]
    assert before_verify >= 1

    # Pipeline auto-assign: individual_id only, no human is_correct decision.
    db.add(
        Annotation(
            detection_id=quoll.id,
            annotator="megadescriptor_reid",
            individual_id="02Q2",
            notes="auto re-ID sim=0.900 gap=0.100",
        )
    )
    await db.commit()

    after = await client.get("/api/detections/review-queue")
    assert after.status_code == 200
    assert after.json()["verify_quolls"] == before_verify

    listing = await client.get(
        "/api/detections/",
        params={"species": "quoll", "review_status": "unreviewed", "per_page": 50},
    )
    assert listing.status_code == 200
    ids = [d["id"] for d in listing.json()["items"]]
    assert quoll.id in ids


@pytest.mark.asyncio
async def test_human_verify_removes_quoll_from_unreviewed(
    client: AsyncClient, sample_data, db: AsyncSession
):
    quoll = sample_data["detections"][0]
    db.add(
        Annotation(
            detection_id=quoll.id,
            annotator="reviewer@example.com",
            is_correct=True,
        )
    )
    await db.commit()

    listing = await client.get(
        "/api/detections/",
        params={"species": "quoll", "review_status": "unreviewed", "per_page": 50},
    )
    ids = [d["id"] for d in listing.json()["items"]]
    assert quoll.id not in ids

    queue = await client.get("/api/detections/review-queue")
    assert queue.json()["verify_quolls"] == 0
