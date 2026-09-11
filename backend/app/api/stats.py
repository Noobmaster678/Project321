"""Dashboard statistics API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_, union
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.image import Image
from backend.app.models.detection import Detection
from backend.app.models.annotation import Annotation
from backend.app.models.camera import Camera
from backend.app.models.collection import Collection
from backend.app.models.individual import Individual
from backend.app.models.sighting import Sighting
from backend.app.schemas.schemas import DashboardStats
from backend.app.services.reid_utils import quoll_sql_filter

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("/", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get overview statistics for the dashboard."""
    total_images = (await db.execute(select(func.count(Image.id)))).scalar() or 0
    processed = (await db.execute(
        select(func.count(Image.id)).where(Image.processed == True)  # noqa: E712
    )).scalar() or 0
    total_detections = (await db.execute(select(func.count(Detection.id)))).scalar() or 0
    animal_detections = (await db.execute(
        select(func.count(Detection.id)).where(Detection.category == "animal")
    )).scalar() or 0
    quoll_detections = (await db.execute(
        select(func.count(Detection.id)).where(Detection.species.ilike("%quoll%"))
    )).scalar() or 0
    # Count distinct individuals from both the individuals table AND annotation-based IDs,
    # since detections annotated with an individual_id in review do not always have a
    # corresponding row in the individuals table.
    _ind_table_q = select(Individual.individual_id.label("iid"))
    _ann_ids_q = (
        select(Annotation.individual_id.label("iid"))
        .join(Detection, Annotation.detection_id == Detection.id)
        .where(
            Annotation.individual_id.isnot(None),
            Annotation.individual_id != "",
            Detection.species.isnot(None),
            quoll_sql_filter(),
        )
    )
    _combined = union(_ind_table_q, _ann_ids_q).subquery()
    total_individuals = (
        await db.execute(select(func.count()).select_from(_combined))
    ).scalar() or 0
    total_cameras = (await db.execute(select(func.count(Camera.id)))).scalar() or 0
    total_collections = (await db.execute(select(func.count(Collection.id)))).scalar() or 0

    # Detections that have no annotation yet
    annotated_ids = select(Annotation.detection_id).distinct()
    pending_review = (await db.execute(
        select(func.count(Detection.id)).where(
            and_(Detection.category == "animal", Detection.id.notin_(annotated_ids))
        )
    )).scalar() or 0

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
        pending_review=pending_review,
    )


@router.get("/cameras")
async def camera_stats(db: AsyncSession = Depends(get_db)):
    """Camera locations with image/detection counts and last upload time."""
    query = (
        select(
            Camera.id, Camera.name, Camera.latitude, Camera.longitude,
            func.count(Image.id).label("image_count"),
            func.max(Image.captured_at).label("last_upload"),
        )
        .outerjoin(Image, Image.camera_id == Camera.id)
        .group_by(Camera.id, Camera.name, Camera.latitude, Camera.longitude)
        .order_by(Camera.name)
    )
    rows = (await db.execute(query)).all()

    result = []
    for r in rows:
        cam_id, name, lat, lon, img_count, last_upload = r
        det_count_q = (
            select(func.count(Detection.id))
            .join(Image, Image.id == Detection.image_id)
            .where(Image.camera_id == cam_id)
        )
        det_count = (await db.execute(det_count_q)).scalar() or 0
        result.append({
            "id": cam_id, "name": name, "latitude": lat, "longitude": lon,
            "image_count": img_count, "detection_count": det_count,
            "last_upload": str(last_upload) if last_upload else None,
        })
    return result


@router.get("/collections")
async def collection_stats(db: AsyncSession = Depends(get_db)):
    """Image count per collection."""
    query = (
        select(Collection.name, func.count(Image.id).label("image_count"))
        .outerjoin(Image, Image.collection_id == Collection.id)
        .group_by(Collection.id, Collection.name)
        .order_by(Collection.name)
    )
    rows = (await db.execute(query)).all()
    return [{"name": r[0], "image_count": r[1]} for r in rows]


def _storage_url(rel: str | None) -> str | None:
    if not rel:
        return None
    return "/storage/" + rel.replace("\\", "/")


def _detection_gallery_score(det: Detection) -> tuple[int, int]:
    """Prefer a quoll crop when a CSV sighting is image-level (no detection_id)."""
    species = (det.species or "").lower()
    return (
        1 if "quoll" in species else 0,
        1 if det.crop_path else 0,
    )


def _gallery_item(img: Image, det: Detection | None) -> dict:
    crop_rel = det.crop_path if det else None
    thumb_rel = img.thumbnail_path
    file_rel = img.file_path
    display = _storage_url(thumb_rel) or _storage_url(crop_rel) or _storage_url(file_rel)
    return {
        "image_id": img.id,
        "detection_id": det.id if det else None,
        "captured_at": str(img.captured_at) if img.captured_at else None,
        "thumb_url": _storage_url(thumb_rel),
        "crop_url": _storage_url(crop_rel),
        "display_url": display,
    }


@router.get("/individuals")
async def individual_stats(db: AsyncSession = Depends(get_db)):
    """List individuals from `individuals` table merged with IDs assigned in review (annotations).

    Uploading images alone does not create rows here; assigning an individual ID on a quoll
    detection in Review does. CSV import may populate `individuals` + sightings separately.
    """
    by_key: dict[str, dict] = {}
    result = await db.execute(select(Individual).order_by(Individual.individual_id))
    inds = result.scalars().all()
    for ind in inds:
        by_key[ind.individual_id] = {
            "individual_id": ind.individual_id,
            "species": ind.species,
            "profile_lead": ind.profile_lead,
            "notes": ind.notes,
            "first_seen": ind.first_seen,
            "last_seen": ind.last_seen,
            "total_sightings": ind.total_sightings or 0,
        }

    ann_q = (
        select(
            Annotation.individual_id,
            func.count(Detection.id).label("cnt"),
            func.min(Image.captured_at).label("first"),
            func.max(Image.captured_at).label("last"),
        )
        .join(Detection, Annotation.detection_id == Detection.id)
        .join(Image, Detection.image_id == Image.id)
        .where(
            Annotation.individual_id.isnot(None),
            Annotation.individual_id != "",
            Detection.species.isnot(None),
            quoll_sql_filter(),
        )
        .group_by(Annotation.individual_id)
    )
    ann_rows = (await db.execute(ann_q)).all()
    for row in ann_rows:
        iid, cnt, first, last = row
        if not iid:
            continue
        ann_cnt = int(cnt)
        if iid not in by_key:
            sp = (
                await db.execute(
                    select(Detection.species)
                    .join(Annotation, Annotation.detection_id == Detection.id)
                    .where(Annotation.individual_id == iid)
                    .limit(1)
                )
            ).scalar_one_or_none()
            by_key[iid] = {
                "individual_id": iid,
                "species": sp or "Spotted-tailed Quoll",
                "profile_lead": None,
                "notes": None,
                "first_seen": first,
                "last_seen": last,
                "total_sightings": ann_cnt,
            }
        else:
            cur = by_key[iid]
            cur["total_sightings"] = max(cur["total_sightings"], ann_cnt)
            if first is not None:
                if cur["first_seen"] is None or first < cur["first_seen"]:
                    cur["first_seen"] = first
            if last is not None:
                if cur["last_seen"] is None or last > cur["last_seen"]:
                    cur["last_seen"] = last

    out = sorted(by_key.values(), key=lambda x: x["individual_id"])
    return out


@router.get("/individuals/{individual_id}/gallery")
async def individual_gallery(individual_id: str, db: AsyncSession = Depends(get_db)):
    """Thumbnails/crops from CSV sightings merged with review annotations.

    Bulk CSV import writes ``Sighting`` rows with ``detection_id=NULL`` and never
    generates thumbnails. The ML pipeline stores crops on ``Detection`` but does
    not back-link those rows onto the sighting. Joining only on
    ``Sighting.detection_id`` therefore left ``display_url`` empty, and a
    non-empty sightings result skipped annotation-assigned crops entirely.
    """
    ind_row = (
        await db.execute(select(Individual).where(Individual.individual_id == individual_id))
    ).scalar_one_or_none()

    items: list[dict] = []
    seen: set[tuple[int, int | None]] = set()
    used_images: set[int] = set()
    sources: set[str] = set()

    def _append(img: Image, det: Detection | None, source: str) -> None:
        key = (img.id, det.id if det else None)
        if key in seen:
            return
        if det is None and img.id in used_images:
            return
        if det is not None and (img.id, None) in seen:
            items[:] = [
                it for it in items
                if not (it["image_id"] == img.id and it["detection_id"] is None)
            ]
            seen.discard((img.id, None))
        seen.add(key)
        used_images.add(img.id)
        sources.add(source)
        items.append(_gallery_item(img, det))

    if ind_row:
        sight_q = (
            select(Sighting, Image, Detection)
            .join(Image, Sighting.image_id == Image.id)
            .outerjoin(Detection, Sighting.detection_id == Detection.id)
            .where(Sighting.individual_id == ind_row.id)
            .order_by(Image.captured_at.desc().nulls_last(), Sighting.id.desc())
        )
        pending_images: list[Image] = []
        for _sight, img, det in (await db.execute(sight_q)).all():
            if det is None:
                pending_images.append(img)
            else:
                _append(img, det, "sightings")

        if pending_images:
            img_ids = list({im.id for im in pending_images})
            det_rows = (
                await db.execute(select(Detection).where(Detection.image_id.in_(img_ids)))
            ).scalars().all()
            best_by_image: dict[int, Detection] = {}
            for det in det_rows:
                prev = best_by_image.get(det.image_id)
                if prev is None or _detection_gallery_score(det) > _detection_gallery_score(prev):
                    best_by_image[det.image_id] = det
            for img in pending_images:
                _append(img, best_by_image.get(img.id), "sightings")

    ann_q = (
        select(Detection, Image)
        .join(Image, Detection.image_id == Image.id)
        .join(Annotation, Annotation.detection_id == Detection.id)
        .where(Annotation.individual_id == individual_id)
        .order_by(Image.captured_at.desc().nulls_last(), Detection.id.desc())
    )
    for det, img in (await db.execute(ann_q)).all():
        _append(img, det, "annotations")

    if "sightings" in sources and "annotations" in sources:
        src = "merged"
    elif "sightings" in sources:
        src = "sightings"
    elif "annotations" in sources:
        src = "annotations"
    else:
        src = "none"

    items.sort(key=lambda it: it["captured_at"] or "", reverse=True)
    return {"individual_id": individual_id, "items": items, "source": src}


@router.get("/individuals/{individual_id}/timeline")
async def individual_timeline(individual_id: str, db: AsyncSession = Depends(get_db)):
    """Chronological timeline and per-month encounter totals for one individual."""
    q = (
        select(
            Detection.id,
            Image.captured_at,
            Camera.name,
            Camera.latitude,
            Camera.longitude,
        )
        .join(Image, Detection.image_id == Image.id)
        .outerjoin(Camera, Camera.id == Image.camera_id)
        .join(Annotation, Annotation.detection_id == Detection.id)
        .where(Annotation.individual_id == individual_id)
        .order_by(Image.captured_at.asc().nullslast(), Detection.id.asc())
    )
    rows = (await db.execute(q)).all()
    events = []
    by_month: dict[str, int] = {}
    for det_id, captured_at, cam_name, lat, lon in rows:
        month_key = None
        if captured_at:
            month_key = captured_at.strftime("%Y-%m")
            by_month[month_key] = by_month.get(month_key, 0) + 1
        events.append(
            {
                "detection_id": int(det_id),
                "captured_at": str(captured_at) if captured_at else None,
                "camera_name": cam_name,
                "latitude": float(lat) if lat is not None else None,
                "longitude": float(lon) if lon is not None else None,
            }
        )
    monthly_counts = [{"month": k, "sightings": by_month[k]} for k in sorted(by_month.keys())]
    return {"individual_id": individual_id, "events": events, "monthly_counts": monthly_counts}
