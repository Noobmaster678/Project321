"""Regression tests for camera-trap independent event grouping."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.camera import Camera
from backend.app.models.image import Image
from backend.app.utils.event_grouping import EVENT_GAP_SECONDS, assign_event_ids


@pytest.mark.asyncio
async def test_assign_event_ids_continues_existing_nearby_event(db: AsyncSession):
    """Incremental processing must not split a still-open event.

    Trigger: image A is assigned event_id during batch 1; image B from the same
    camera arrives later within EVENT_GAP_SECONDS and is processed in batch 2.
    Before the fix, B received a brand-new event_id because A was skipped while
    the counter stayed at max(event_id)+1.
    """
    camera = Camera(name="CAM-EVT-1")
    db.add(camera)
    await db.flush()

    t0 = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
    first = Image(
        filename="a.jpg",
        file_path="uploads/a.jpg",
        camera_id=camera.id,
        captured_at=t0,
        event_id=7,
        processed=True,
    )
    second = Image(
        filename="b.jpg",
        file_path="uploads/b.jpg",
        camera_id=camera.id,
        captured_at=t0 + timedelta(seconds=EVENT_GAP_SECONDS // 2),
        event_id=None,
        processed=True,
    )
    db.add_all([first, second])
    await db.flush()

    minted = await assign_event_ids(db)
    await db.commit()

    assert minted == 0
    assert second.event_id == 7


@pytest.mark.asyncio
async def test_assign_event_ids_starts_new_event_after_gap(db: AsyncSession):
    """Images beyond the gap must still mint a fresh independent event."""
    camera = Camera(name="CAM-EVT-2")
    db.add(camera)
    await db.flush()

    t0 = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
    first = Image(
        filename="a.jpg",
        file_path="uploads/gap_a.jpg",
        camera_id=camera.id,
        captured_at=t0,
        event_id=3,
        processed=True,
    )
    second = Image(
        filename="b.jpg",
        file_path="uploads/gap_b.jpg",
        camera_id=camera.id,
        captured_at=t0 + timedelta(seconds=EVENT_GAP_SECONDS + 1),
        event_id=None,
        processed=True,
    )
    db.add_all([first, second])
    await db.flush()

    minted = await assign_event_ids(db)
    await db.commit()

    assert minted == 1
    assert second.event_id == 4
    assert second.event_id != first.event_id
