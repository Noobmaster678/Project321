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

    Incremental runs must continue an existing nearby event instead of minting a
    new ID whenever prior images are already assigned. Otherwise batch N+1 can
    split one ecological event across IDs and inflate independent-event / RAI
    reports.

    Returns the number of newly minted event IDs in this pass.
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
    next_event_id = current_max + 1
    current_event: int | None = None

    prev_camera = None
    prev_time = None
    minted = 0

    for img in images:
        if img.event_id is not None:
            # Adopt the existing assignment so later unassigned images in the
            # same camera/time window join that event instead of a new one.
            current_event = img.event_id
            prev_camera = img.camera_id
            prev_time = img.captured_at
            continue

        needs_new_event = (
            current_event is None
            or prev_camera != img.camera_id
            or prev_time is None
            or img.captured_at is None
            or (img.captured_at - prev_time).total_seconds() > EVENT_GAP_SECONDS
        )
        if needs_new_event:
            current_event = next_event_id
            next_event_id += 1
            minted += 1

        img.event_id = current_event
        prev_camera = img.camera_id
        prev_time = img.captured_at

    return minted
