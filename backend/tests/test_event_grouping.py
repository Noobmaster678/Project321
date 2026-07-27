"""Regression tests for independent-event grouping."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.camera import Camera
from backend.app.models.image import Image
from backend.app.utils.event_grouping import EVENT_GAP_SECONDS, assign_event_ids


@pytest.mark.asyncio
async def test_null_camera_images_split_on_time_gap(db: AsyncSession):
    """Uploads without camera folders must still split events across gaps.

    The UI allows batch upload with no camera assignment. Treating camera_id=NULL
    as "no previous camera" skipped the gap check and collapsed every unassigned
    image into a single independent event.
    """
    base = datetime(2026, 1, 1, 12, 0, 0)
    images = [
        Image(filename="a.jpg", file_path="uploads/a.jpg", camera_id=None, captured_at=base),
        Image(
            filename="b.jpg",
            file_path="uploads/b.jpg",
            camera_id=None,
            captured_at=base + timedelta(seconds=EVENT_GAP_SECONDS // 2),
        ),
        Image(
            filename="c.jpg",
            file_path="uploads/c.jpg",
            camera_id=None,
            captured_at=base + timedelta(days=2),
        ),
        Image(
            filename="d.jpg",
            file_path="uploads/d.jpg",
            camera_id=None,
            captured_at=base + timedelta(days=5),
        ),
    ]
    db.add_all(images)
    await db.commit()

    created = await assign_event_ids(db)
    await db.commit()
    for img in images:
        await db.refresh(img)

    assert created == 3
    assert images[0].event_id == images[1].event_id
    assert images[2].event_id != images[0].event_id
    assert images[3].event_id != images[2].event_id
    assert images[3].event_id != images[0].event_id


@pytest.mark.asyncio
async def test_named_cameras_still_split_on_camera_change(db: AsyncSession):
    cam_a = Camera(name="1A", latitude=-35.0, longitude=150.0)
    cam_b = Camera(name="1B", latitude=-35.1, longitude=150.1)
    db.add_all([cam_a, cam_b])
    await db.flush()

    base = datetime(2026, 2, 1, 8, 0, 0)
    images = [
        Image(
            filename="a1.jpg",
            file_path="uploads/a1.jpg",
            camera_id=cam_a.id,
            captured_at=base,
        ),
        Image(
            filename="b1.jpg",
            file_path="uploads/b1.jpg",
            camera_id=cam_b.id,
            captured_at=base + timedelta(seconds=10),
        ),
        Image(
            filename="b2.jpg",
            file_path="uploads/b2.jpg",
            camera_id=cam_b.id,
            captured_at=base + timedelta(seconds=20),
        ),
    ]
    db.add_all(images)
    await db.commit()

    await assign_event_ids(db)
    await db.commit()
    for img in images:
        await db.refresh(img)

    assert images[0].event_id != images[1].event_id
    assert images[1].event_id == images[2].event_id
