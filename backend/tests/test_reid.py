"""Tests for re-ID API safety gates."""
import pytest
from httpx import AsyncClient

from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_reid_suggestions_requires_auth(client: AsyncClient, sample_data):
    det_id = sample_data["detections"][0].id

    resp = await client.get(f"/api/reid/detections/{det_id}/suggestions")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reid_suggestions_auth_checks_detection(client: AsyncClient, test_user):
    resp = await client.get(
        "/api/reid/detections/9999/suggestions",
        headers=auth_header(test_user),
    )

    assert resp.status_code == 404
