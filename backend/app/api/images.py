"""Image browsing and querying API endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.session import get_db
from backend.app.models.image import Image
from backend.app.models.detection import Detection
from backend.app.models.camera import Camera
from backend.app.models.collection import Collection
from backend.app.schemas.schemas import ImageOut, ImageDetail, PaginatedResponse

router = APIRouter(prefix="/images", tags=["Images"])


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

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    images = result.scalars().all()

    return PaginatedResponse(
        items=[ImageOut.model_validate(img) for img in images],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page > 0 else 0,
    )


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image(image_id: int, db: AsyncSession = Depends(get_db)):
    """Get image details including camera, collection, and detections."""
    query = (
        select(Image)
        .where(Image.id == image_id)
        .options(
            selectinload(Image.camera),
            selectinload(Image.collection),
            selectinload(Image.detections),
        )
    )
    result = await db.execute(query)
    image = result.scalar_one_or_none()
    if not image:
        from fastapi import HTTPException
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
        .where(Detection.species == species)
        .distinct()
    )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    images = result.scalars().all()

    return PaginatedResponse(
        items=[ImageOut.model_validate(img) for img in images],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page > 0 else 0,
    )
