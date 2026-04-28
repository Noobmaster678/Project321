"""Individual profile CRUD endpoints (manual re-ID workflow)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.detection import Detection
from backend.app.models.individual import Individual
from backend.app.schemas.schemas import IndividualOut, IndividualCreate
from backend.app.models.user import User
from backend.app.utils.dependencies import get_current_user

router = APIRouter(prefix="/individuals", tags=["Individuals"])


@router.post("/", response_model=IndividualOut, status_code=status.HTTP_201_CREATED)
async def create_individual(
    payload: IndividualCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an Individual profile with required left/right reference detections."""
    # (Auth) user dependency ensures only logged-in ecologists/admins can create profiles.
    _ = user

    # Uniqueness: individual_id
    existing = (
        await db.execute(select(func.count(Individual.id)).where(Individual.individual_id == payload.individual_id))
    ).scalar() or 0
    if existing > 0:
        raise HTTPException(status_code=409, detail="Individual ID already exists")

    # Validate detections exist
    left = (
        await db.execute(select(Detection).where(Detection.id == payload.ref_left_detection_id))
    ).scalar_one_or_none()
    if not left:
        raise HTTPException(status_code=400, detail="Left reference detection not found")
    right = (
        await db.execute(select(Detection).where(Detection.id == payload.ref_right_detection_id))
    ).scalar_one_or_none()
    if not right:
        raise HTTPException(status_code=400, detail="Right reference detection not found")

    # Basic sanity: left/right must be different detections
    if left.id == right.id:
        raise HTTPException(status_code=400, detail="Left and right reference detections must be different")

    ind = Individual(
        individual_id=payload.individual_id,
        species=payload.species,
        name=payload.name,
        ref_left_detection_id=payload.ref_left_detection_id,
        ref_right_detection_id=payload.ref_right_detection_id,
    )
    db.add(ind)
    await db.flush()
    await db.refresh(ind)
    return IndividualOut.model_validate(ind)

