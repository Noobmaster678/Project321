"""Tests for individual profile lifecycle behavior."""
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.individual import Individual
from backend.tests.conftest import auth_header


@pytest.mark.asyncio
async def test_delete_individual_purges_reid_gallery(
    client: AsyncClient,
    admin_user,
    db: AsyncSession,
    monkeypatch,
):
    db.add(Individual(individual_id="02Q2", species="Spotted-tailed Quoll"))
    await db.commit()
    purge = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "backend.app.api.individuals.remove_individual_from_reid_gallery",
        purge,
    )

    response = await client.delete(
        "/api/individuals/02Q2",
        headers=auth_header(admin_user),
    )

    assert response.status_code == 204
    purge.assert_awaited_once_with("02Q2")
    assert (await client.get("/api/individuals/02Q2")).status_code == 404


@pytest.mark.asyncio
async def test_delete_individual_preserves_profile_when_gallery_purge_fails(
    client: AsyncClient,
    admin_user,
    db: AsyncSession,
    monkeypatch,
):
    db.add(Individual(individual_id="02Q2", species="Spotted-tailed Quoll"))
    await db.commit()
    monkeypatch.setattr(
        "backend.app.api.individuals.remove_individual_from_reid_gallery",
        AsyncMock(return_value=False),
    )

    response = await client.delete(
        "/api/individuals/02Q2",
        headers=auth_header(admin_user),
    )

    assert response.status_code == 503
    assert (await client.get("/api/individuals/02Q2")).status_code == 200
