"""Dashboard statistics API endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.image import Image
from backend.app.models.detection import Detection
from backend.app.models.camera import Camera
from backend.app.models.collection import Collection
from backend.app.models.individual import Individual
from backend.app.schemas.schemas import DashboardStats

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("/", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get overview statistics for the dashboard."""
    total_images = (await db.execute(select(func.count(Image.id)))).scalar() or 0
    processed = (await db.execute(
        select(func.count(Image.id)).where(Image.processed == True)
    )).scalar() or 0
    total_detections = (await db.execute(select(func.count(Detection.id)))).scalar() or 0
    animal_detections = (await db.execute(
        select(func.count(Detection.id)).where(Detection.category == "animal")
    )).scalar() or 0
    quoll_detections = (await db.execute(
        select(func.count(Detection.id)).where(Detection.species == "Spotted-tailed Quoll")
    )).scalar() or 0
    total_individuals = (await db.execute(select(func.count(Individual.id)))).scalar() or 0
    total_cameras = (await db.execute(select(func.count(Camera.id)))).scalar() or 0
    total_collections = (await db.execute(select(func.count(Collection.id)))).scalar() or 0

    return DashboardStats(
        total_images=total_images,
        processed_images=processed,
        unprocessed_images=total_images - processed,
        total_detections=total_detections,
        total_animals=animal_detections,
        quoll_detections=quoll_detections,
        total_individuals=total_individuals,
        total_cameras=total_cameras,
        total_collections=total_collections,
        processing_percent=round((processed / total_images * 100), 2) if total_images > 0 else 0.0,
    )


@router.get("/cameras")
async def camera_stats(db: AsyncSession = Depends(get_db)):
    """Image count per camera."""
    query = (
        select(Camera.name, Camera.latitude, Camera.longitude, func.count(Image.id).label("image_count"))
        .outerjoin(Image, Image.camera_id == Camera.id)
        .group_by(Camera.id, Camera.name, Camera.latitude, Camera.longitude)
        .order_by(Camera.name)
    )
    result = await db.execute(query)
    rows = result.all()
    return [
        {"name": r[0], "latitude": r[1], "longitude": r[2], "image_count": r[3]}
        for r in rows
    ]


@router.get("/collections")
async def collection_stats(db: AsyncSession = Depends(get_db)):
    """Image count per collection."""
    query = (
        select(Collection.name, func.count(Image.id).label("image_count"))
        .outerjoin(Image, Image.collection_id == Collection.id)
        .group_by(Collection.id, Collection.name)
        .order_by(Collection.name)
    )
    result = await db.execute(query)
    rows = result.all()
    return [{"name": r[0], "image_count": r[1]} for r in rows]


@router.get("/individuals")
async def individual_stats(db: AsyncSession = Depends(get_db)):
    """List all identified individuals with sighting counts."""
    query = select(Individual).order_by(Individual.individual_id)
    result = await db.execute(query)
    individuals = result.scalars().all()
    return [
        {
            "individual_id": ind.individual_id,
            "species": ind.species,
            "first_seen": ind.first_seen,
            "last_seen": ind.last_seen,
            "total_sightings": ind.total_sightings,
        }
        for ind in individuals
    ]
