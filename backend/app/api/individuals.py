"""Individual profile CRUD endpoints (manual re-ID workflow)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, update as sa_update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.annotation import Annotation
from backend.app.models.detection import Detection
from backend.app.models.individual import Individual
from backend.app.models.sighting import Sighting
from backend.app.schemas.schemas import IndividualOut, IndividualCreate, IndividualProfileUpdate
from backend.app.models.user import User
from backend.app.utils.dependencies import get_current_user, require_role

router = APIRouter(prefix="/individuals", tags=["Individuals"])


@router.get("/{individual_id}", response_model=IndividualOut)
async def get_individual(
    individual_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get one individual profile by public ID (e.g. 02Q2)."""
    ind = (
        await db.execute(select(Individual).where(Individual.individual_id == individual_id))
    ).scalar_one_or_none()
    if not ind:
        raise HTTPException(status_code=404, detail="Individual not found")
    return IndividualOut.model_validate(ind)


@router.patch("/{individual_id}", response_model=IndividualOut)
async def update_individual_profile(
    individual_id: str,
    payload: IndividualProfileUpdate,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update profile lead and notes (admin only). Creates a minimal row if needed."""
    ind = (
        await db.execute(select(Individual).where(Individual.individual_id == individual_id))
    ).scalar_one_or_none()
    if not ind:
        ind = Individual(
            individual_id=individual_id,
            species="Spotted-tailed Quoll",
        )
        db.add(ind)
        await db.flush()

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(ind, field, value)

    await db.flush()
    await db.refresh(ind)
    return IndividualOut.model_validate(ind)


@router.post("/", response_model=IndividualOut, status_code=status.HTTP_201_CREATED)
async def create_individual(
    payload: IndividualCreate,
    user: User = Depends(require_role("admin", "researcher")),
    db: AsyncSession = Depends(get_db),
):
    """Create an Individual profile. Restricted to researcher / admin roles."""
    _ = user

    # Uniqueness: individual_id
    existing = (
        await db.execute(select(func.count(Individual.id)).where(Individual.individual_id == payload.individual_id))
    ).scalar() or 0
    if existing > 0:
        raise HTTPException(status_code=409, detail="Individual ID already exists")

    # Validate reference detections if provided
    ref_left_id = None
    ref_right_id = None

    if payload.ref_left_detection_id is not None:
        left = (
            await db.execute(select(Detection).where(Detection.id == payload.ref_left_detection_id))
        ).scalar_one_or_none()
        if not left:
            raise HTTPException(status_code=400, detail="Left reference detection not found")
        ref_left_id = left.id

    if payload.ref_right_detection_id is not None:
        right = (
            await db.execute(select(Detection).where(Detection.id == payload.ref_right_detection_id))
        ).scalar_one_or_none()
        if not right:
            raise HTTPException(status_code=400, detail="Right reference detection not found")
        ref_right_id = right.id

    # If both provided, they must be different
    if ref_left_id is not None and ref_right_id is not None and ref_left_id == ref_right_id:
        raise HTTPException(status_code=400, detail="Left and right reference detections must be different")

    ind = Individual(
        individual_id=payload.individual_id,
        species=payload.species,
        name=payload.name,
        notes=payload.notes,
        profile_lead=payload.profile_lead,
        ref_left_detection_id=ref_left_id,
        ref_right_detection_id=ref_right_id,
    )
    db.add(ind)
    await db.flush()
    await db.refresh(ind)
    return IndividualOut.model_validate(ind)


@router.delete("/{individual_id}", status_code=204)
async def delete_individual(
    individual_id: str,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Delete an individual profile (admin only).

    Nulls out all annotation assignments pointing to this ID and removes all
    sighting rows before deleting the profile row itself.
    """
    ind = (
        await db.execute(select(Individual).where(Individual.individual_id == individual_id))
    ).scalar_one_or_none()
    assignment_count = (
        await db.execute(
            select(func.count(Annotation.id)).where(Annotation.individual_id == individual_id)
        )
    ).scalar() or 0
    if not ind and assignment_count == 0:
        raise HTTPException(status_code=404, detail="Individual not found")

    await db.execute(
        sa_update(Annotation)
        .where(Annotation.individual_id == individual_id)
        .values(individual_id=None)
    )
    if ind:
        await db.execute(
            sa_delete(Sighting).where(Sighting.individual_id == ind.id)
        )
        await db.delete(ind)
    await db.flush()
