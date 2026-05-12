"""Tests for dataset export authorization."""
import pytest
from httpx import AsyncClient

from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_metadata_export_requires_authentication(client: AsyncClient, sample_data):
    resp = await client.get("/api/exports/metadata")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_metadata_export_forbids_reviewer(client: AsyncClient, test_user, sample_data):
    resp = await client.get("/api/exports/metadata", headers=auth_header(test_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_metadata_export_allows_admin(client: AsyncClient, admin_user, sample_data):
    resp = await client.get("/api/exports/metadata", headers=auth_header(admin_user))
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "detection_id" in resp.text
