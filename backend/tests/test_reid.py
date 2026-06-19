"""Tests for re-identification API endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_reid_suggestions_require_auth(client: AsyncClient):
    resp = await client.get("/api/reid/detections/1/suggestions")
    assert resp.status_code == 401
