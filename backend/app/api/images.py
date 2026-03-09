"""Image browsing, upload, and batch processing API endpoints."""
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.image import Image
from backend.app.models.detection import Detection
from backend.app.models.camera import Camera
from backend.app.models.collection import Collection
from backend.app.models.job import ProcessingJob
from backend.app.models.user import User
from backend.app.schemas.schemas import (
    ImageOut, ImageDetail, PaginatedResponse, BatchUploadResponse, JobStatus,
)
from backend.app.utils.dependencies import get_current_user, get_optional_user

router = APIRouter(prefix="/images", tags=["Images"])

UPLOAD_DIR = settings.STORAGE_ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---- Read endpoints -------------------------------------------------------

@router.get("/", response_model=PaginatedResponse)
async def list_images(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    camera_id: int | None = None,
    collection_id: int | None = None,
    processed: bool | None = None,
    has_animal: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List images with optional filters and pagination."""
    query = select(Image)
    if camera_id is not None:
        query = query.where(Image.camera_id == camera_id)
    if collection_id is not None:
        query = query.where(Image.collection_id == collection_id)
    if processed is not None:
        query = query.where(Image.processed == processed)
    if has_animal is not None:
        query = query.where(Image.has_animal == has_animal)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    images = result.scalars().all()

    return PaginatedResponse(
        items=[ImageOut.model_validate(img) for img in images],
        total=total, page=page, per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page > 0 else 0,
    )


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: int, db: AsyncSession = Depends(get_db)):
    """Poll processing job progress."""
    job = (await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    pct = (job.processed_images / job.total_images * 100) if job.total_images > 0 else 0.0
    resp = JobStatus.model_validate(job)
    resp.percent = round(pct, 2)
    return resp


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image(image_id: int, db: AsyncSession = Depends(get_db)):
    """Get image details including camera, collection, and detections."""
    query = (
        select(Image)
        .where(Image.id == image_id)
        .options(selectinload(Image.camera), selectinload(Image.collection), selectinload(Image.detections))
    )
    image = (await db.execute(query)).scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return ImageDetail.model_validate(image)


@router.get("/by-species/{species}", response_model=PaginatedResponse)
async def images_by_species(
    species: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Find images that contain detections of a specific species."""
    query = (
        select(Image)
        .join(Detection, Detection.image_id == Image.id)
        .where(Detection.species.ilike(f"%{species}%"))
        .distinct()
    )
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    images = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[ImageOut.model_validate(img) for img in images],
        total=total, page=page, per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page > 0 else 0,
    )


# ---- Upload endpoints -----------------------------------------------------

@router.post("/upload", response_model=ImageOut)
async def upload_image(
    file: UploadFile = File(...),
    camera_id: int | None = None,
    collection_id: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a single image, save to storage, create DB record, queue ML processing."""
    ext = Path(file.filename or "unknown.jpg").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        raise HTTPException(status_code=400, detail="Unsupported image format")

    dest = UPLOAD_DIR / (file.filename or "unknown.jpg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    rel_path = str(dest.relative_to(settings.STORAGE_ROOT))
    image = Image(
        filename=file.filename or "unknown.jpg",
        file_path=rel_path,
        camera_id=camera_id,
        collection_id=collection_id,
    )
    db.add(image)
    await db.flush()
    await db.refresh(image)

    try:
        from backend.worker.tasks import process_image_task
        process_image_task.delay(image.id)
    except Exception:
        pass  # Celery may not be running; image stays unprocessed

    return ImageOut.model_validate(image)


@router.post("/upload-batch", response_model=BatchUploadResponse)
async def upload_batch(
    files: list[UploadFile] = File(...),
    camera_id: int | None = None,
    collection_id: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple images and queue a batch processing job."""
    image_ids = []
    for f in files:
        ext = Path(f.filename or "unknown.jpg").suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png"):
            continue

        dest = UPLOAD_DIR / (f.filename or "unknown.jpg")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)

        rel_path = str(dest.relative_to(settings.STORAGE_ROOT))
        image = Image(
            filename=f.filename or "unknown.jpg",
            file_path=rel_path,
            camera_id=camera_id,
            collection_id=collection_id,
        )
        db.add(image)
        await db.flush()
        image_ids.append(image.id)

    job = ProcessingJob(
        batch_name=f"batch-upload-{len(image_ids)}-files",
        status="queued",
        total_images=len(image_ids),
        created_by=user.id,
    )
    db.add(job)
    await db.flush()

    try:
        from backend.worker.tasks import process_batch_task
        task = process_batch_task.delay(job.id, image_ids)
        job.celery_task_id = task.id
    except Exception:
        pass

    return BatchUploadResponse(job_id=job.id, files_received=len(image_ids), status="queued")
