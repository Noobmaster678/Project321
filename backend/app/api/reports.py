"""Report generation and export API endpoints."""
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.deployment import Deployment
from backend.app.models.detection import Detection
from backend.app.models.image import Image
from backend.app.models.camera import Camera
from backend.app.schemas.schemas import ReportOut, RAIReport, RAIEntry
from backend.app.services.report_service import (
    generate_summary_report, generate_batch_report,
    export_report_csv, export_report_json,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary", response_model=ReportOut)
async def summary_report(
    species: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Overall platform summary report with species distribution, hourly activity, camera counts."""
    report = await generate_summary_report(db, species_filter=species)
    return report


@router.get("/batch/{job_id}")
async def batch_report(job_id: int, db: AsyncSession = Depends(get_db)):
    """Report for a specific batch processing job."""
    report = await generate_batch_report(db, job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Job not found")
    return report


@router.get("/rai", response_model=RAIReport)
async def rai_report(db: AsyncSession = Depends(get_db)):
    """Compute Relative Abundance Index per species using independent events and trap-nights."""
    total_trap_nights = (await db.execute(select(func.sum(Deployment.trap_nights)))).scalar() or 0.0
    total_deployments = (await db.execute(select(func.count(Deployment.id)))).scalar() or 0
    total_cameras = (await db.execute(select(func.count(distinct(Deployment.camera_id))))).scalar() or 0

    entries: list[RAIEntry] = []
    if total_trap_nights > 0:
        q = (
            select(
                Detection.species,
                func.count(distinct(Image.event_id)).label("events"),
            )
            .join(Image, Image.id == Detection.image_id)
            .where(Detection.species.isnot(None), Image.event_id.isnot(None))
            .group_by(Detection.species)
            .order_by(func.count(distinct(Image.event_id)).desc())
        )
        for row in (await db.execute(q)).all():
            sp_name, events = row
            entries.append(RAIEntry(
                species=sp_name,
                independent_events=events,
                total_trap_nights=round(total_trap_nights, 2),
                rai=round((events / total_trap_nights) * 100, 4),
            ))

    # Camera occupancy: per species, fraction of cameras that detected it
    camera_occupancy: list[dict] = []
    if total_cameras > 0:
        occ_q = (
            select(
                Detection.species,
                func.count(distinct(Image.camera_id)).label("cams"),
            )
            .join(Image, Image.id == Detection.image_id)
            .where(Detection.species.isnot(None))
            .group_by(Detection.species)
        )
        for row in (await db.execute(occ_q)).all():
            sp_name, cams = row
            camera_occupancy.append({
                "species": sp_name,
                "cameras_detected": cams,
                "total_cameras": total_cameras,
                "occupancy": round(cams / total_cameras, 4),
            })

    return RAIReport(
        total_trap_nights=round(total_trap_nights, 2),
        total_deployments=total_deployments,
        total_cameras=total_cameras,
        entries=entries,
        camera_occupancy=camera_occupancy,
    )


@router.get("/export")
async def export_report(
    format: str = Query("csv", pattern="^(csv|json)$"),
    species: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Export the summary report as CSV or JSON file download."""
    report = await generate_summary_report(db, species_filter=species)

    if format == "csv":
        content = export_report_csv(report)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=wildlife_report.csv"},
        )
    else:
        content = export_report_json(report)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=wildlife_report.json"},
        )
