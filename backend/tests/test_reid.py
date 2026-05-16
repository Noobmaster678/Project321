"""Tests for re-identification suggestion endpoints."""
import pytest
from httpx import AsyncClient

from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_reid_suggestions_require_auth(client: AsyncClient, sample_data):
    det_id = sample_data["detections"][0].id

    resp = await client.get(f"/api/reid/detections/{det_id}/suggestions")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reid_suggestions_authenticated_request_reaches_validation(
    client: AsyncClient,
    test_user,
    sample_data,
):
    det_id = sample_data["detections"][0].id

    resp = await client.get(
        f"/api/reid/detections/{det_id}/suggestions",
        headers=auth_header(test_user),
    )

    assert resp.status_code == 400
    assert "crop" in resp.json()["detail"].lower()
