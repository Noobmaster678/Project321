"""Tests for re-identification endpoints."""
import pytest
from httpx import AsyncClient

from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_reid_suggestions_require_auth(client: AsyncClient):
    """Generating and logging re-ID suggestions requires a logged-in user."""
    resp = await client.get("/api/reid/detections/999/suggestions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reid_suggestions_authenticated_request_reaches_lookup(client: AsyncClient, test_user):
    resp = await client.get(
        "/api/reid/detections/999/suggestions",
        headers=auth_header(test_user),
    )
    assert resp.status_code == 404
