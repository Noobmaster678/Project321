"""Tests for individual profile endpoints."""
import pytest
from httpx import AsyncClient

from backend.app.models.annotation import Annotation
from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_delete_annotation_only_individual_clears_assignments(client: AsyncClient, db, admin_user, sample_data):
    det = sample_data["detections"][0]
    ann = Annotation(detection_id=det.id, is_correct=True, individual_id="02Q2")
    db.add(ann)
    await db.commit()

    resp = await client.delete("/api/individuals/02Q2", headers=auth_header(admin_user))
    assert resp.status_code == 204

    await db.refresh(ann)
    assert ann.individual_id is None


@pytest.mark.asyncio
async def test_delete_unknown_individual_returns_404(client: AsyncClient, admin_user):
    resp = await client.delete("/api/individuals/__missing__", headers=auth_header(admin_user))
    assert resp.status_code == 404
