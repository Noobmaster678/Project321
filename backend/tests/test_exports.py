"""Tests for dataset export endpoints."""
import pytest
from httpx import AsyncClient

from backend.app.models.annotation import Annotation
from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_exports_require_auth(client: AsyncClient):
    resp = await client.get("/api/exports/quoll-detections")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_quoll_export_individual_filter_deduplicates_annotations(client: AsyncClient, db, test_user, sample_data):
    det = sample_data["detections"][0]
    db.add_all([
        Annotation(detection_id=det.id, individual_id="02Q2", is_correct=True),
        Annotation(detection_id=det.id, individual_id="02Q2", is_correct=True),
    ])
    await db.commit()

    resp = await client.get(
        "/api/exports/quoll-detections",
        params={"format": "json", "individual_id": "02Q2"},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["detection_id"] == det.id


@pytest.mark.asyncio
async def test_metadata_export_individual_filter_deduplicates_annotations(client: AsyncClient, db, test_user, sample_data):
    det = sample_data["detections"][0]
    db.add_all([
        Annotation(detection_id=det.id, individual_id="02Q2", is_correct=True),
        Annotation(detection_id=det.id, individual_id="02Q2", is_correct=True),
    ])
    await db.commit()

    resp = await client.get(
        "/api/exports/metadata",
        params={"format": "json", "individual_id": "02Q2"},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["detection_id"] == det.id
