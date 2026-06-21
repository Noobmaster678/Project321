"""Tests for re-identification endpoints."""
import pytest
from httpx import AsyncClient

from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_reid_suggestions_require_auth(client: AsyncClient):
    resp = await client.get("/api/reid/detections/1/suggestions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reid_suggestions_authenticated_not_found(client: AsyncClient, test_user):
    resp = await client.get("/api/reid/detections/9999/suggestions", headers=auth_header(test_user))
    assert resp.status_code == 404
