"""Annotation CRUD endpoints for ecologist review workflow."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.models.individual import Individual
from backend.app.models.user import User
from backend.app.schemas.schemas import AnnotationCreate, AnnotationUpdate, AnnotationOut
from backend.app.services.reid_learning import resolve_reid_suggestions, incremental_update_from_detection
from backend.app.utils.dependencies import get_current_user

router = APIRouter(prefix="/annotations", tags=["Annotations"])


@router.post("/", response_model=AnnotationOut, status_code=status.HTTP_201_CREATED)
async def create_annotation(
    payload: AnnotationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an annotation (species correction, individual ID, retraining flag)."""
    det = (await db.execute(select(Detection).where(Detection.id == payload.detection_id))).scalar_one_or_none()
    if not det:
        raise HTTPException(status_code=404, detail="Detection not found")

    existing_assignment_ids: set[str] = set()
    if payload.individual_id:
        ind = (await db.execute(
            select(Individual).where(Individual.individual_id == payload.individual_id)
        )).scalar_one_or_none()
        if not ind:
            raise HTTPException(
                status_code=404,
                detail=f"Individual '{payload.individual_id}' does not exist. Create the profile first.",
            )
        existing_assignment_ids = await _active_individual_ids(db, payload.detection_id)

    ann = Annotation(
        detection_id=payload.detection_id,
        annotator=user.email,
        corrected_species=payload.corrected_species,
        is_correct=payload.is_correct,
        notes=payload.notes,
        individual_id=payload.individual_id,
        flag_for_retraining=payload.flag_for_retraining,
    )
    db.add(ann)
    await db.flush()
    if payload.individual_id:
        await _clear_individual_assignments(db, payload.detection_id, keep_annotation_id=ann.id)
        await resolve_reid_suggestions(
            db,
            detection_id=payload.detection_id,
            chosen_individual_id=payload.individual_id,
            annotator=user.email,
        )
        if payload.individual_id not in existing_assignment_ids:
            await incremental_update_from_detection(
                db,
                detection_id=payload.detection_id,
                individual_id=payload.individual_id,
            )
    await db.refresh(ann)
    return AnnotationOut.model_validate(ann)


@router.get("/by-detection/{detection_id}", response_model=list[AnnotationOut])
async def get_annotations_for_detection(
    detection_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all annotations for a specific detection."""
    result = await db.execute(
        select(Annotation).where(Annotation.detection_id == detection_id).order_by(Annotation.created_at.desc())
    )
    return [AnnotationOut.model_validate(a) for a in result.scalars().all()]


@router.put("/{annotation_id}", response_model=AnnotationOut)
async def update_annotation(
    annotation_id: int,
    payload: AnnotationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing annotation."""
    ann = (await db.execute(select(Annotation).where(Annotation.id == annotation_id))).scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")

    before_individual = ann.individual_id
    existing_assignment_ids = await _active_individual_ids(db, ann.detection_id, exclude_annotation_id=ann.id)
    updates = payload.model_dump(exclude_unset=True)
    after_individual = updates.get("individual_id", before_individual)
    if after_individual:
        ind = (
            await db.execute(
                select(Individual).where(Individual.individual_id == after_individual)
            )
        ).scalar_one_or_none()
        if not ind:
            raise HTTPException(
                status_code=404,
                detail=f"Individual '{after_individual}' does not exist. Create the profile first.",
            )

    for field, value in updates.items():
        setattr(ann, field, value)
    ann.annotator = user.email

    await db.flush()
    if "individual_id" in updates:
        if ann.individual_id:
            await _clear_individual_assignments(db, ann.detection_id, keep_annotation_id=ann.id)
            await resolve_reid_suggestions(
                db,
                detection_id=ann.detection_id,
                chosen_individual_id=ann.individual_id,
                annotator=user.email,
            )
            if ann.individual_id != before_individual and ann.individual_id not in existing_assignment_ids:
                await incremental_update_from_detection(
                    db,
                    detection_id=ann.detection_id,
                    individual_id=ann.individual_id,
                )
        else:
            await _clear_individual_assignments(db, ann.detection_id)
    await db.refresh(ann)
    return AnnotationOut.model_validate(ann)


async def _active_individual_ids(
    db: AsyncSession,
    detection_id: int,
    exclude_annotation_id: int | None = None,
) -> set[str]:
    """Return the non-empty individual IDs currently assigned to a detection."""
    query = select(Annotation.individual_id).where(
        Annotation.detection_id == detection_id,
        Annotation.individual_id.isnot(None),
        Annotation.individual_id != "",
    )
    if exclude_annotation_id is not None:
        query = query.where(Annotation.id != exclude_annotation_id)
    result = await db.execute(query)
    return {str(iid) for iid in result.scalars().all()}


async def _clear_individual_assignments(
    db: AsyncSession,
    detection_id: int,
    keep_annotation_id: int | None = None,
) -> None:
    """Keep at most one active individual assignment for a detection."""
    query = select(Annotation).where(
        Annotation.detection_id == detection_id,
        Annotation.individual_id.isnot(None),
        Annotation.individual_id != "",
    )
    if keep_annotation_id is not None:
        query = query.where(Annotation.id != keep_annotation_id)
    rows = (await db.execute(query)).scalars().all()
    for row in rows:
        row.individual_id = None
    if rows:
        await db.flush()
