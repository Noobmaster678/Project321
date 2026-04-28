"""Tests for admin-only endpoints: user management, system metrics."""
from pathlib import Path

import pytest
from httpx import AsyncClient

from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_list_users_admin(client: AsyncClient, admin_user, test_user):
    resp = await client.get("/api/admin/users", headers=auth_header(admin_user))
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert admin_user.email in emails
    assert test_user.email in emails


@pytest.mark.asyncio
async def test_list_users_non_admin(client: AsyncClient, test_user):
    resp = await client.get("/api/admin/users", headers=auth_header(test_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_role(client: AsyncClient, admin_user, test_user):
    resp = await client.patch(
        f"/api/admin/users/{test_user.id}/role",
        params={"role": "researcher"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "researcher"


@pytest.mark.asyncio
async def test_change_role_invalid(client: AsyncClient, admin_user, test_user):
    resp = await client.patch(
        f"/api/admin/users/{test_user.id}/role",
        params={"role": "superuser"},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_system_metrics(client: AsyncClient, admin_user, sample_data):
    resp = await client.get("/api/admin/system-metrics", headers=auth_header(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_images"] == 5
    assert data["total_users"] >= 1


@pytest.mark.asyncio
async def test_reid_backfill_forbidden(client: AsyncClient, test_user):
    resp = await client.post(
        "/api/admin/reid-backfill",
        json={"mode": "missing_only", "limit": 10, "run_async": False},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reid_backfill_no_gallery(client: AsyncClient, admin_user, monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.reid_backfill.reid_gallery_path",
        lambda: Path("/__nonexistent_quoll_gallery__.pt"),
    )
    resp = await client.post(
        "/api/admin/reid-backfill",
        json={"mode": "missing_only", "limit": 10, "run_async": False},
        headers=auth_header(admin_user),
    )
    assert resp.status_code == 400
    assert "gallery" in resp.json()["detail"].lower()
