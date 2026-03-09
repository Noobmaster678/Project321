"""Detection querying API endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.detection import Detection
from backend.app.schemas.schemas import DetectionOut, PaginatedResponse

router = APIRouter(prefix="/detections", tags=["Detections"])


@router.get("/", response_model=PaginatedResponse)
async def list_detections(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    species: str | None = None,
    min_confidence: float | None = None,
    image_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List detections with optional filters."""
    query = select(Detection)

    if species is not None:
        query = query.where(Detection.species == species)
    if min_confidence is not None:
        query = query.where(Detection.classification_confidence >= min_confidence)
    if image_id is not None:
        query = query.where(Detection.image_id == image_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    detections = result.scalars().all()

    return PaginatedResponse(
        items=[DetectionOut.model_validate(d) for d in detections],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page > 0 else 0,
    )


@router.get("/species-counts")
async def species_counts(db: AsyncSession = Depends(get_db)):
    """Get count of detections per species."""
    query = (
        select(Detection.species, func.count(Detection.id).label("count"))
        .where(Detection.species.isnot(None))
        .group_by(Detection.species)
        .order_by(func.count(Detection.id).desc())
    )
    result = await db.execute(query)
    rows = result.all()
    return [{"species": row[0], "count": row[1]} for row in rows]
