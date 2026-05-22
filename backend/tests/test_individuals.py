"""Tests for individual profile endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation
from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_delete_annotation_only_individual_clears_assignments(
    client: AsyncClient,
    admin_user,
    sample_data,
    db: AsyncSession,
):
    det_id = sample_data["detections"][0].id
    db.add(Annotation(detection_id=det_id, annotator="legacy", individual_id="LEGACY-Q"))
    await db.commit()

    resp = await client.delete("/api/individuals/LEGACY-Q", headers=auth_header(admin_user))
    assert resp.status_code == 204

    anns = (await client.get(f"/api/annotations/by-detection/{det_id}")).json()
    assert anns
    assert all(ann["individual_id"] is None for ann in anns)


@pytest.mark.asyncio
async def test_delete_unknown_individual_still_404(client: AsyncClient, admin_user):
    resp = await client.delete("/api/individuals/NOPE", headers=auth_header(admin_user))
    assert resp.status_code == 404
