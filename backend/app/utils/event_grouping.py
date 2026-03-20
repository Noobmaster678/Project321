"""Event grouping for camera trap image sequences.

Groups images into independent events based on camera station and time gap.
Images within EVENT_GAP_SECONDS at the same camera are considered one event.
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.image import Image

EVENT_GAP_SECONDS = 60


async def assign_event_ids(db: AsyncSession, collection_id: int | None = None) -> int:
    """Assign event_id to images based on camera + time proximity.

    Returns the total number of events created.
    """
    query = (
        select(Image)
        .where(Image.captured_at.isnot(None))
        .order_by(Image.camera_id, Image.captured_at)
    )
    if collection_id is not None:
        query = query.where(Image.collection_id == collection_id)

    result = await db.execute(query)
    images = result.scalars().all()

    if not images:
        return 0

    max_event_q = select(func.max(Image.event_id))
    current_max = (await db.execute(max_event_q)).scalar() or 0
    event_id = current_max + 1

    prev_camera = None
    prev_time = None

    for img in images:
        if img.event_id is not None:
            prev_camera = img.camera_id
            prev_time = img.captured_at
            continue

        if (
            prev_camera is not None
            and img.camera_id == prev_camera
            and prev_time is not None
            and img.captured_at is not None
        ):
            delta = (img.captured_at - prev_time).total_seconds()
            if delta > EVENT_GAP_SECONDS:
                event_id += 1
        elif prev_camera != img.camera_id:
            event_id += 1

        img.event_id = event_id
        prev_camera = img.camera_id
        prev_time = img.captured_at

    return event_id - current_max
