"""Detection querying API endpoints."""
from datetime import datetime as dt

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.session import get_db
from backend.app.models.detection import Detection
from backend.app.models.annotation import Annotation
from backend.app.models.image import Image
from backend.app.schemas.schemas import DetectionOut, DetectionDetail, PaginatedResponse, CameraOut, ImageOut, AnnotationOut

router = APIRouter(prefix="/detections", tags=["Detections"])


@router.get("/", response_model=PaginatedResponse)
async def list_detections(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    species: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    image_id: int | None = None,
    camera_id: int | None = None,
    collection_id: int | None = None,
    date_from: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    date_to: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    review_status: str | None = Query(None, description="unreviewed, verified, corrected, flagged"),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List detections with optional filters."""
    needs_join = camera_id is not None or collection_id is not None or date_from is not None or date_to is not None
    query = select(Detection)
    if needs_join:
        query = query.join(Image, Image.id == Detection.image_id)

    if species is not None:
        query = query.where(Detection.species.ilike(f"%{species}%"))
    if min_confidence is not None:
        query = query.where(Detection.classification_confidence >= min_confidence)
    if max_confidence is not None:
        query = query.where(Detection.classification_confidence <= max_confidence)
    if image_id is not None:
        query = query.where(Detection.image_id == image_id)
    if category is not None:
        query = query.where(Detection.category == category)
    if camera_id is not None:
        query = query.where(Image.camera_id == camera_id)
    if collection_id is not None:
        query = query.where(Image.collection_id == collection_id)
    if date_from is not None:
        try:
            dfrom = dt.fromisoformat(date_from)
            query = query.where(Image.captured_at >= dfrom)
        except ValueError:
            pass
    if date_to is not None:
        try:
            dto = dt.fromisoformat(date_to)
            query = query.where(Image.captured_at <= dto)
        except ValueError:
            pass
    if review_status is not None:
        if review_status == "unreviewed":
            annotated_ids = select(Annotation.detection_id).distinct()
            query = query.where(Detection.id.notin_(annotated_ids))
        elif review_status == "verified":
            verified_ids = select(Annotation.detection_id).where(Annotation.is_correct == True).distinct()  # noqa: E712
            query = query.where(Detection.id.in_(verified_ids))
        elif review_status == "corrected":
            corrected_ids = select(Annotation.detection_id).where(Annotation.is_correct == False).distinct()  # noqa: E712
            query = query.where(Detection.id.in_(corrected_ids))
        elif review_status == "flagged":
            flagged_ids = select(Annotation.detection_id).where(Annotation.flag_for_retraining == True).distinct()  # noqa: E712
            query = query.where(Detection.id.in_(flagged_ids))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    detections = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=[DetectionOut.model_validate(d) for d in detections],
        total=total, page=page, per_page=per_page,
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
    rows = (await db.execute(query)).all()
    return [{"species": row[0], "count": row[1]} for row in rows]


@router.get("/review-queue")
async def review_queue(db: AsyncSession = Depends(get_db)):
    """Get counts for each review category used in the Pending Review page."""
    annotated_ids = select(Annotation.detection_id).distinct()

    quoll_unreviewed = (await db.execute(
        select(func.count(Detection.id)).where(
            and_(
                Detection.species.ilike("%quoll%"),
                Detection.id.notin_(annotated_ids),
            )
        )
    )).scalar() or 0

    low_conf = (await db.execute(
        select(func.count(Detection.id)).where(
            and_(
                Detection.category == "animal",
                Detection.id.notin_(annotated_ids),
                (Detection.detection_confidence < 0.5) | (Detection.classification_confidence < 0.5),
            )
        )
    )).scalar() or 0

    empty_unchecked = (await db.execute(
        select(func.count(Image.id)).where(
            and_(Image.processed == True, Image.has_animal == False)  # noqa: E712
        )
    )).scalar() or 0

    verified_quoll_ids = (
        select(Annotation.detection_id)
        .where(Annotation.is_correct == True, Annotation.individual_id.is_(None))  # noqa: E712
        .distinct()
    )
    quolls_needing_id = (await db.execute(
        select(func.count(Detection.id)).where(
            and_(
                Detection.species.ilike("%quoll%"),
                Detection.id.in_(verified_quoll_ids),
            )
        )
    )).scalar() or 0

    total_pending = (await db.execute(
        select(func.count(Detection.id)).where(
            and_(Detection.category == "animal", Detection.id.notin_(annotated_ids))
        )
    )).scalar() or 0

    return {
        "verify_quolls": quoll_unreviewed,
        "low_confidence": low_conf,
        "empty_check": empty_unchecked,
        "assign_individual": quolls_needing_id,
        "total_pending": total_pending,
    }


@router.get("/{detection_id}", response_model=DetectionDetail)
async def get_detection(detection_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single detection with image, camera, and annotations."""
    query = (
        select(Detection)
        .where(Detection.id == detection_id)
        .options(
            selectinload(Detection.image).selectinload(Image.camera),
            selectinload(Detection.annotations),
        )
    )
    det = (await db.execute(query)).scalar_one_or_none()
    if not det:
        raise HTTPException(status_code=404, detail="Detection not found")

    return DetectionDetail(
        **DetectionOut.model_validate(det).model_dump(),
        image=ImageOut.model_validate(det.image) if det.image else None,
        camera=CameraOut.model_validate(det.image.camera) if det.image and det.image.camera else None,
        annotations=[AnnotationOut.model_validate(a) for a in det.annotations],
    )
