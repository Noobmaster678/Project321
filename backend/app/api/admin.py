"""Admin-only endpoints for user management, system metrics, and retraining."""
import io
import os
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.models.image import Image
from backend.app.models.detection import Detection
from backend.app.models.annotation import Annotation
from backend.app.models.missed_correction import MissedDetectionCorrection
from backend.app.models.job import ProcessingJob
from backend.app.models.model_version import ModelVersion
from backend.app.schemas.schemas import UserOut, ModelVersionOut, ModelVersionCreate
from backend.app.utils.dependencies import require_role

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.patch("/users/{user_id}/role", response_model=UserOut)
async def change_user_role(
    user_id: int,
    role: str,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Change a user's role (admin only)."""
    if role not in ("admin", "researcher", "reviewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = role
    await db.flush()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/system-metrics")
async def system_metrics(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """System health metrics (admin only)."""
    total_images = (await db.execute(select(func.count(Image.id)))).scalar() or 0
    processed = (await db.execute(select(func.count(Image.id)).where(Image.processed == True))).scalar() or 0  # noqa: E712
    total_detections = (await db.execute(select(func.count(Detection.id)))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    pending_jobs = (await db.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.status.in_(["queued", "processing"]))
    )).scalar() or 0

    db_path = Path("wildlife.db")
    db_size_mb = round(db_path.stat().st_size / 1024 / 1024, 2) if db_path.exists() else 0

    storage_size_mb = 0
    if settings.STORAGE_ROOT.exists():
        total = sum(f.stat().st_size for f in settings.STORAGE_ROOT.rglob("*") if f.is_file())
        storage_size_mb = round(total / 1024 / 1024, 2)

    return {
        "total_images": total_images,
        "processed_images": processed,
        "unprocessed_images": total_images - processed,
        "total_detections": total_detections,
        "total_users": total_users,
        "pending_jobs": pending_jobs,
        "db_size_mb": db_size_mb,
        "storage_size_mb": storage_size_mb,
    }


# ---- Retraining dataset export -------------------------------------------

@router.get("/export-retraining-dataset")
async def export_retraining_dataset(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Export a ZIP of training data organized as ImageFolder (species_name/crop.jpg).

    Includes:
    - Confirmed correct crops  -> label = detection.species
    - Corrected crops          -> label = annotation.corrected_species
    - Missed detection images  -> label = correction.species (full image, not cropped)
    """
    # Confirmed correct detections (annotated with is_correct=True)
    correct_q = (
        select(Detection, Annotation)
        .join(Annotation, Annotation.detection_id == Detection.id)
        .where(Annotation.is_correct == True, Detection.crop_path.isnot(None))  # noqa: E712
    )
    correct_rows = (await db.execute(correct_q)).all()

    # Corrected detections (annotated with is_correct=False)
    corrected_q = (
        select(Detection, Annotation)
        .join(Annotation, Annotation.detection_id == Detection.id)
        .where(
            Annotation.is_correct == False,  # noqa: E712
            Annotation.corrected_species.isnot(None),
            Detection.crop_path.isnot(None),
        )
    )
    corrected_rows = (await db.execute(corrected_q)).all()

    # Missed detections (user-drawn boxes on empty images)
    missed_q = (
        select(MissedDetectionCorrection)
        .options(selectinload(MissedDetectionCorrection.image))
        .where(MissedDetectionCorrection.flag_for_retraining == True)  # noqa: E712
    )
    missed_rows = (await db.execute(missed_q)).scalars().all()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        seen: set[str] = set()

        for det, ann in correct_rows:
            label = (det.species or "unknown").replace("/", "_").strip()
            crop_full = settings.STORAGE_ROOT / det.crop_path
            if crop_full.exists():
                arcname = f"confirmed/{label}/{Path(det.crop_path).name}"
                if arcname not in seen:
                    seen.add(arcname)
                    zf.write(crop_full, arcname)

        for det, ann in corrected_rows:
            label = (ann.corrected_species or "unknown").replace("/", "_").strip()
            crop_full = settings.STORAGE_ROOT / det.crop_path
            if crop_full.exists():
                arcname = f"corrected/{label}/{Path(det.crop_path).name}"
                if arcname not in seen:
                    seen.add(arcname)
                    zf.write(crop_full, arcname)

        for mc in missed_rows:
            label = (mc.species or "unknown").replace("/", "_").strip()
            if mc.image and mc.image.file_path:
                img_full = settings.STORAGE_ROOT / mc.image.file_path
                if not img_full.exists():
                    img_full = settings.DATASET_ROOT / mc.image.file_path
                if img_full.exists():
                    arcname = f"missed/{label}/img_{mc.image_id}_mc_{mc.id}{img_full.suffix}"
                    if arcname not in seen:
                        seen.add(arcname)
                        zf.write(img_full, arcname)

        # Write a manifest CSV
        import csv
        manifest = io.StringIO()
        writer = csv.writer(manifest)
        writer.writerow(["source", "species", "archive_path"])
        for path in sorted(seen):
            parts = path.split("/")
            writer.writerow([parts[0], parts[1] if len(parts) > 1 else "", path])
        zf.writestr("manifest.csv", manifest.getvalue())

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=retraining_dataset.zip"},
    )


@router.get("/retraining-stats")
async def retraining_stats(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Summary of available retraining data."""
    confirmed = (await db.execute(
        select(func.count(Annotation.id)).where(Annotation.is_correct == True)  # noqa: E712
    )).scalar() or 0
    corrected = (await db.execute(
        select(func.count(Annotation.id)).where(
            Annotation.is_correct == False, Annotation.corrected_species.isnot(None)  # noqa: E712
        )
    )).scalar() or 0
    missed = (await db.execute(
        select(func.count(MissedDetectionCorrection.id)).where(
            MissedDetectionCorrection.flag_for_retraining == True  # noqa: E712
        )
    )).scalar() or 0
    flagged = (await db.execute(
        select(func.count(Annotation.id)).where(Annotation.flag_for_retraining == True)  # noqa: E712
    )).scalar() or 0

    return {
        "confirmed_correct": confirmed,
        "corrected_labels": corrected,
        "missed_detections": missed,
        "flagged_for_retraining": flagged,
        "total_training_samples": confirmed + corrected + missed,
    }


# ---- Model version management ---------------------------------------------

@router.get("/model-versions", response_model=list[ModelVersionOut])
async def list_model_versions(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all registered model versions."""
    result = await db.execute(select(ModelVersion).order_by(ModelVersion.created_at.desc()))
    return [ModelVersionOut.model_validate(m) for m in result.scalars().all()]


@router.post("/model-versions", response_model=ModelVersionOut, status_code=201)
async def create_model_version(
    payload: ModelVersionCreate,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Register a new model version."""
    mv = ModelVersion(
        name=payload.name,
        model_type=payload.model_type,
        model_path=payload.model_path,
        base_model=payload.base_model,
        notes=payload.notes,
    )
    db.add(mv)
    await db.flush()
    await db.refresh(mv)
    return ModelVersionOut.model_validate(mv)


@router.patch("/model-versions/{version_id}/activate", response_model=ModelVersionOut)
async def activate_model_version(
    version_id: int,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Set a model version as the active one (deactivates others of the same type)."""
    mv = (await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))).scalar_one_or_none()
    if not mv:
        raise HTTPException(status_code=404, detail="Model version not found")

    others = (await db.execute(
        select(ModelVersion).where(ModelVersion.model_type == mv.model_type, ModelVersion.is_active == True)  # noqa: E712
    )).scalars().all()
    for other in others:
        other.is_active = False

    mv.is_active = True
    await db.flush()
    await db.refresh(mv)
    return ModelVersionOut.model_validate(mv)


@router.get("/dashboard-stats")
async def get_dashboard_stats(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Combined stats + placeholder cards for the admin dashboard UI (mirrors AdminPage.tsx)."""
    total_images = (await db.execute(select(func.count(Image.id)))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    pending_jobs = (await db.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.status.in_(["queued", "processing"]))
    )).scalar() or 0

    return {
        "stats": [
            {"label": "Total images", "value": f"{total_images:,}", "color": "green"},
            {"label": "Total users", "value": f"{total_users:,}", "color": "green"},
            {"label": "Jobs in queue / processing", "value": f"{pending_jobs:,}", "color": "yellow"},
            {"label": "Unresolved issues (placeholder)", "value": "—", "color": "red"},
        ],
        "recent_sightings": [
            {"id": "#S-1042", "tag": "98% Confidence", "status": "Review", "img": "https://via.placeholder.com/400x300?text=Sighting+1"},
            {"id": "#S-902", "tag": "Conflict", "status": "Review", "img": "https://via.placeholder.com/400x300?text=Sighting+2"},
            {"id": "#S-1209", "tag": "New Individual", "status": "Review", "img": "https://via.placeholder.com/400x300?text=Sighting+3"},
            {"id": "#S-3008", "tag": "No Animal", "status": "Review", "img": "https://via.placeholder.com/400x300?text=Sighting+4"},
            {"id": "#S-523", "tag": "Vulnerable", "status": "Review", "img": "https://via.placeholder.com/400x300?text=Sighting+5"},
            {"id": "#S-1337", "tag": "Verified", "status": "Review", "img": "https://via.placeholder.com/400x300?text=Sighting+6"},
        ],
    }
