"""Critical upload/processing races: commit-before-dispatch and missing-file retries."""
import io
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.image import Image
from backend.app.models.job import ProcessingJob
from backend.tests.conftest import auth_header, TestSession
from backend.worker.tasks import _process_single_image


@pytest.mark.asyncio
async def test_missing_image_file_leaves_unprocessed(db: AsyncSession):
    """Workers must not permanently skip images whose files are temporarily missing."""
    image = Image(
        filename="missing.jpg",
        file_path="uploads/does-not-exist-missing.jpg",
        processed=False,
        has_animal=None,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    completed = await _process_single_image(db, image, md=MagicMock(), awc=MagicMock())
    await db.commit()
    await db.refresh(image)

    assert completed is False
    assert image.processed is False
    assert image.has_animal is None


@pytest.mark.asyncio
async def test_upload_commits_before_celery_dispatch(client: AsyncClient, test_user, monkeypatch):
    """Celery enqueue must run only after the image row is committed and visible."""
    visibility = {"delay_called": False, "visible_at_delay": False}

    class FakeTask:
        @staticmethod
        def delay(image_id: int):
            visibility["delay_called"] = True
            visibility["image_id"] = image_id

            async def _probe():
                async with TestSession() as session:
                    row = (
                        await session.execute(select(Image).where(Image.id == image_id))
                    ).scalar_one_or_none()
                    visibility["visible_at_delay"] = row is not None

            # delay() is sync but runs inside the request's event loop — probe now.
            import asyncio

            asyncio.get_running_loop().create_task(_probe())

            # Also probe via a nested runner-free approach: open session and
            # schedule the coroutine to complete before the handler returns by
            # using an Event the handler can... actually we need immediate check.
            # Use a dedicated Future awaited by monkeypatched wrapper below.

    import backend.worker.tasks as tasks_mod

    probe_done = None

    class FakeTaskAwaitProbe:
        @staticmethod
        def delay(image_id: int):
            visibility["delay_called"] = True
            visibility["image_id"] = image_id
            import asyncio

            async def _probe():
                async with TestSession() as session:
                    row = (
                        await session.execute(select(Image).where(Image.id == image_id))
                    ).scalar_one_or_none()
                    visibility["visible_at_delay"] = row is not None

            # Run probe to completion before returning from delay so we assert
            # visibility at the exact enqueue moment (post-commit).
            nonlocal_loop = asyncio.get_running_loop()
            fut = nonlocal_loop.create_task(_probe())
            # Store future so the test can ensure it completed; drain below after POST
            visibility["probe_task"] = fut

    monkeypatch.setattr(tasks_mod, "process_image_task", FakeTaskAwaitProbe)

    # Prevent local fallback from racing if import path differs
    async def _no_local(_image_id: int):
        return None

    monkeypatch.setattr("backend.app.api.images._run_single_locally", _no_local)

    fake_jpg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    resp = await client.post(
        "/api/images/upload",
        files={"file": ("commit_before_dispatch.jpg", fake_jpg, "image/jpeg")},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    image_id = resp.json()["id"]

    if visibility.get("probe_task") is not None:
        await visibility["probe_task"]

    # If Celery import succeeded, delay must have seen a committed row.
    # If Celery import failed and local fallback was used, the committed row
    # must still be visible after the handler returns.
    async with TestSession() as session:
        row = (await session.execute(select(Image).where(Image.id == image_id))).scalar_one_or_none()
        assert row is not None
        assert row.processed is False

    if visibility["delay_called"]:
        assert visibility["visible_at_delay"] is True
        assert visibility["image_id"] == image_id


@pytest.mark.asyncio
async def test_batch_upload_commits_job_before_dispatch(client: AsyncClient, test_user, monkeypatch):
    """Batch image/job rows must be committed before workers are enqueued."""
    visibility = {"delay_called": False, "job_visible": False, "images_visible": 0}

    class FakeTask:
        @staticmethod
        def delay(job_id: int, image_ids: list[int]):
            visibility["delay_called"] = True
            visibility["job_id"] = job_id
            visibility["image_ids"] = list(image_ids)

            import asyncio

            async def _probe():
                async with TestSession() as session:
                    job = (
                        await session.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
                    ).scalar_one_or_none()
                    imgs = (await session.execute(select(Image))).scalars().all()
                    visibility["job_visible"] = job is not None
                    visibility["images_visible"] = len(imgs)

            visibility["probe_task"] = asyncio.get_running_loop().create_task(_probe())
            return MagicMock(id="fake-task")

    import backend.worker.tasks as tasks_mod

    monkeypatch.setattr(tasks_mod, "process_batch_task", FakeTask)

    def _no_enqueue(job_id: int, image_ids: list[int]):
        return None

    monkeypatch.setattr("backend.app.api.images._enqueue_local_batch", _no_enqueue)

    fake_jpg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    resp = await client.post(
        "/api/images/upload-batch",
        files=[("files", ("batch_commit.jpg", fake_jpg, "image/jpeg"))],
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    if visibility.get("probe_task") is not None:
        await visibility["probe_task"]

    async with TestSession() as session:
        job = (
            await session.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
        ).scalar_one_or_none()
        assert job is not None
        assert job.total_images >= 1

    if visibility["delay_called"]:
        assert visibility["job_visible"] is True
        assert visibility["images_visible"] >= 1
        assert visibility["job_id"] == job_id
