"""Report generation service — aggregates DB data into report dicts."""
import csv
import io
import json
from datetime import date

from sqlalchemy import select, func, extract, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.image import Image
from backend.app.models.detection import Detection
from backend.app.models.annotation import Annotation
from backend.app.models.camera import Camera
from backend.app.models.deployment import Deployment
from backend.app.models.job import ProcessingJob
from backend.app.services.reid_utils import quoll_sql_filter


async def generate_summary_report(
    db: AsyncSession,
    species_filter: str | None = None,
    camera_ids: list[int] | None = None,
    collection_ids: list[int] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    camera_name: str | None = None,
    individual_id: str | None = None,
) -> dict:
    """Generate a full platform summary report."""
    img_filter = select(Image.id)
    if camera_ids:
        img_filter = img_filter.where(Image.camera_id.in_(camera_ids))
    if collection_ids:
        img_filter = img_filter.where(Image.collection_id.in_(collection_ids))
    if date_from:
        img_filter = img_filter.where(func.date(Image.captured_at) >= date_from)
    if date_to:
        img_filter = img_filter.where(func.date(Image.captured_at) <= date_to)
    if camera_name:
        img_filter = img_filter.join(Camera, Camera.id == Image.camera_id).where(Camera.name == camera_name)

    base_image_ids = img_filter.subquery()
    total_images = (await db.execute(select(func.count()).select_from(base_image_ids))).scalar() or 0
    processed_images = (await db.execute(
        select(func.count())
        .select_from(Image)
        .where(Image.id.in_(select(base_image_ids.c.id)), Image.processed == True)  # noqa: E712
    )).scalar() or 0
    empty_images = (await db.execute(
        select(func.count())
        .select_from(Image)
        .where(Image.id.in_(select(base_image_ids.c.id)), Image.has_animal == False)  # noqa: E712
    )).scalar() or 0

    det_query = select(Detection.id).join(Image, Image.id == Detection.image_id)
    if camera_ids:
        det_query = det_query.where(Image.camera_id.in_(camera_ids))
    if collection_ids:
        det_query = det_query.where(Image.collection_id.in_(collection_ids))
    if date_from:
        det_query = det_query.where(func.date(Image.captured_at) >= date_from)
    if date_to:
        det_query = det_query.where(func.date(Image.captured_at) <= date_to)
    if camera_name:
        det_query = det_query.join(Camera, Camera.id == Image.camera_id).where(Camera.name == camera_name)
    if species_filter:
        det_query = det_query.where(Detection.species.ilike(f"%{species_filter}%"))
    if individual_id:
        det_query = det_query.join(Annotation, Annotation.detection_id == Detection.id).where(
            Annotation.individual_id.ilike(f"%{individual_id}%")
        )

    det_ids = det_query.subquery()
    det_count_q = select(func.count()).select_from(det_ids)
    total_detections = (await db.execute(det_count_q)).scalar() or 0

    # Species distribution
    sp_q = (
        select(Detection.species, func.count(Detection.id).label("count"))
        .join(Image, Image.id == Detection.image_id)
        .where(Detection.species.isnot(None))
    )
    if camera_ids:
        sp_q = sp_q.where(Image.camera_id.in_(camera_ids))
    if collection_ids:
        sp_q = sp_q.where(Image.collection_id.in_(collection_ids))
    if date_from:
        sp_q = sp_q.where(func.date(Image.captured_at) >= date_from)
    if date_to:
        sp_q = sp_q.where(func.date(Image.captured_at) <= date_to)
    if camera_name:
        sp_q = sp_q.join(Camera, Camera.id == Image.camera_id).where(Camera.name == camera_name)
    if species_filter:
        sp_q = sp_q.where(Detection.species.ilike(f"%{species_filter}%"))
    if individual_id:
        sp_q = sp_q.join(Annotation, Annotation.detection_id == Detection.id).where(
            Annotation.individual_id.ilike(f"%{individual_id}%")
        )
    sp_q = sp_q.group_by(Detection.species).order_by(func.count(Detection.id).desc())
    species_rows = (await db.execute(sp_q)).all()
    species_distribution = [{"species": r[0], "count": r[1]} for r in species_rows]
    total_species = len(species_distribution)

    quoll_detections = sum(r["count"] for r in species_distribution if "quoll" in (r["species"] or "").lower())

    # Confidence stats
    conf_q = select(
        func.avg(Detection.detection_confidence),
        func.avg(Detection.classification_confidence),
    ).join(Image, Image.id == Detection.image_id)
    if camera_ids:
        conf_q = conf_q.where(Image.camera_id.in_(camera_ids))
    if collection_ids:
        conf_q = conf_q.where(Image.collection_id.in_(collection_ids))
    if date_from:
        conf_q = conf_q.where(func.date(Image.captured_at) >= date_from)
    if date_to:
        conf_q = conf_q.where(func.date(Image.captured_at) <= date_to)
    if camera_name:
        conf_q = conf_q.join(Camera, Camera.id == Image.camera_id).where(Camera.name == camera_name)
    if species_filter:
        conf_q = conf_q.where(Detection.species.ilike(f"%{species_filter}%"))
    if individual_id:
        conf_q = conf_q.join(Annotation, Annotation.detection_id == Detection.id).where(
            Annotation.individual_id.ilike(f"%{individual_id}%")
        )
    mean_det_conf, mean_cls_conf = (await db.execute(conf_q)).one()

    # Camera counts
    cam_q = (
        select(Camera.name, func.count(Detection.id).label("count"))
        .join(Image, Image.camera_id == Camera.id)
        .join(Detection, Detection.image_id == Image.id)
    )
    if camera_ids:
        cam_q = cam_q.where(Image.camera_id.in_(camera_ids))
    if collection_ids:
        cam_q = cam_q.where(Image.collection_id.in_(collection_ids))
    if date_from:
        cam_q = cam_q.where(func.date(Image.captured_at) >= date_from)
    if date_to:
        cam_q = cam_q.where(func.date(Image.captured_at) <= date_to)
    if camera_name:
        cam_q = cam_q.where(Camera.name == camera_name)
    if species_filter:
        cam_q = cam_q.where(Detection.species.ilike(f"%{species_filter}%"))
    if individual_id:
        cam_q = cam_q.join(Annotation, Annotation.detection_id == Detection.id).where(
            Annotation.individual_id.ilike(f"%{individual_id}%")
        )
    cam_q = cam_q.group_by(Camera.name).order_by(func.count(Detection.id).desc())
    cam_rows = (await db.execute(cam_q)).all()
    camera_counts = [{"camera": r[0], "detections": r[1]} for r in cam_rows]

    # Hourly activity (from captured_at)
    hourly_q = (
        select(extract("hour", Image.captured_at).label("hour"), func.count(Detection.id).label("count"))
        .join(Detection, Detection.image_id == Image.id)
        .where(Image.captured_at.isnot(None))
    )
    if camera_ids:
        hourly_q = hourly_q.where(Image.camera_id.in_(camera_ids))
    if collection_ids:
        hourly_q = hourly_q.where(Image.collection_id.in_(collection_ids))
    if date_from:
        hourly_q = hourly_q.where(func.date(Image.captured_at) >= date_from)
    if date_to:
        hourly_q = hourly_q.where(func.date(Image.captured_at) <= date_to)
    if camera_name:
        hourly_q = hourly_q.join(Camera, Camera.id == Image.camera_id).where(Camera.name == camera_name)
    if species_filter:
        hourly_q = hourly_q.where(Detection.species.ilike(f"%{species_filter}%"))
    if individual_id:
        hourly_q = hourly_q.join(Annotation, Annotation.detection_id == Detection.id).where(
            Annotation.individual_id.ilike(f"%{individual_id}%")
        )
    hourly_q = hourly_q.group_by("hour").order_by("hour")
    hourly_rows = (await db.execute(hourly_q)).all()
    hourly_activity = [{"hour": int(r[0]), "detections": r[1]} for r in hourly_rows]

    month_q = (
        select(
            extract("year", Image.captured_at).label("year"),
            extract("month", Image.captured_at).label("month"),
            func.count(Detection.id).label("count"),
        )
        .join(Detection, Detection.image_id == Image.id)
        .where(Image.captured_at.isnot(None))
    )
    if camera_ids:
        month_q = month_q.where(Image.camera_id.in_(camera_ids))
    if collection_ids:
        month_q = month_q.where(Image.collection_id.in_(collection_ids))
    if date_from:
        month_q = month_q.where(func.date(Image.captured_at) >= date_from)
    if date_to:
        month_q = month_q.where(func.date(Image.captured_at) <= date_to)
    if camera_name:
        month_q = month_q.join(Camera, Camera.id == Image.camera_id).where(Camera.name == camera_name)
    if species_filter:
        month_q = month_q.where(Detection.species.ilike(f"%{species_filter}%"))
    if individual_id:
        month_q = month_q.join(Annotation, Annotation.detection_id == Detection.id).where(
            Annotation.individual_id.ilike(f"%{individual_id}%")
        )
    month_q = month_q.group_by("year", "month").order_by("year", "month")
    month_rows = (await db.execute(month_q)).all()
    monthly_activity = [
        {
            "month": f"{int(r[0]):04d}-{int(r[1]):02d}",
            "detections": int(r[2]),
        }
        for r in month_rows
    ]

    identified_q = (
        select(
            extract("year", Image.captured_at).label("year"),
            extract("month", Image.captured_at).label("month"),
            Annotation.individual_id,
        )
        .join(Detection, Detection.id == Annotation.detection_id)
        .join(Image, Image.id == Detection.image_id)
        .where(
            Annotation.individual_id.isnot(None),
            Annotation.individual_id != "",
            Detection.species.isnot(None),
            quoll_sql_filter(),
            Image.captured_at.isnot(None),
        )
    )
    if camera_ids:
        identified_q = identified_q.where(Image.camera_id.in_(camera_ids))
    if collection_ids:
        identified_q = identified_q.where(Image.collection_id.in_(collection_ids))
    if date_from:
        identified_q = identified_q.where(func.date(Image.captured_at) >= date_from)
    if date_to:
        identified_q = identified_q.where(func.date(Image.captured_at) <= date_to)
    if camera_name:
        identified_q = identified_q.join(Camera, Camera.id == Image.camera_id).where(Camera.name == camera_name)
    identified_q = identified_q.order_by("year", "month")
    identified_rows = (await db.execute(identified_q)).all()
    by_month: dict[str, set[str]] = {}
    for year, month, iid in identified_rows:
        if not iid:
            continue
        key = f"{int(year):04d}-{int(month):02d}"
        by_month.setdefault(key, set()).add(str(iid))
    identified_quolls_over_time: list[dict] = []
    seen_ids: set[str] = set()
    for month in sorted(by_month.keys()):
        new_ids = by_month[month] - seen_ids
        seen_ids.update(by_month[month])
        identified_quolls_over_time.append(
            {
                "month": month,
                "new_identified": len(new_ids),
                "cumulative_identified": len(seen_ids),
            }
        )

    recent_q = (
        select(
            Detection.id,
            Image.captured_at,
            Detection.species,
            Detection.classification_confidence,
            Camera.latitude,
            Camera.longitude,
        )
        .join(Image, Image.id == Detection.image_id)
        .outerjoin(Camera, Camera.id == Image.camera_id)
        .order_by(Image.captured_at.desc().nulls_last(), Detection.id.desc())
        .limit(25)
    )
    if camera_ids:
        recent_q = recent_q.where(Image.camera_id.in_(camera_ids))
    if collection_ids:
        recent_q = recent_q.where(Image.collection_id.in_(collection_ids))
    if date_from:
        recent_q = recent_q.where(func.date(Image.captured_at) >= date_from)
    if date_to:
        recent_q = recent_q.where(func.date(Image.captured_at) <= date_to)
    if camera_name:
        recent_q = recent_q.where(Camera.name == camera_name)
    if species_filter:
        recent_q = recent_q.where(Detection.species.ilike(f"%{species_filter}%"))
    if individual_id:
        recent_q = recent_q.join(Annotation, Annotation.detection_id == Detection.id).where(
            Annotation.individual_id.ilike(f"%{individual_id}%")
        )
    recent_rows = (await db.execute(recent_q)).all()
    recent_sightings = [
        {
            "detection_id": int(r[0]),
            "captured_at": str(r[1]) if r[1] else None,
            "species": r[2],
            "confidence": round(float(r[3]), 4) if r[3] is not None else None,
            "latitude": float(r[4]) if r[4] is not None else None,
            "longitude": float(r[5]) if r[5] is not None else None,
        }
        for r in recent_rows
    ]

    # RAI: Relative Abundance Index = (independent events / trap-nights) * 100
    total_trap_nights_val = (await db.execute(
        select(func.sum(Deployment.trap_nights))
    )).scalar() or 0.0

    rai_data: list[dict] = []
    if total_trap_nights_val > 0:
        # Count independent events per species using event_id
        event_species_q = (
            select(
                Detection.species,
                func.count(distinct(Image.event_id)).label("events"),
            )
            .join(Image, Image.id == Detection.image_id)
            .where(Detection.species.isnot(None), Image.event_id.isnot(None))
        )
        if camera_ids:
            event_species_q = event_species_q.where(Image.camera_id.in_(camera_ids))
        if collection_ids:
            event_species_q = event_species_q.where(Image.collection_id.in_(collection_ids))
        if date_from:
            event_species_q = event_species_q.where(func.date(Image.captured_at) >= date_from)
        if date_to:
            event_species_q = event_species_q.where(func.date(Image.captured_at) <= date_to)
        if camera_name:
            event_species_q = event_species_q.join(Camera, Camera.id == Image.camera_id).where(Camera.name == camera_name)
        if species_filter:
            event_species_q = event_species_q.where(Detection.species.ilike(f"%{species_filter}%"))
        if individual_id:
            event_species_q = event_species_q.join(Annotation, Annotation.detection_id == Detection.id).where(
                Annotation.individual_id.ilike(f"%{individual_id}%")
            )
        event_species_q = event_species_q.group_by(Detection.species).order_by(func.count(distinct(Image.event_id)).desc())
        event_rows = (await db.execute(event_species_q)).all()
        for row in event_rows:
            sp_name, events = row
            rai_val = round((events / total_trap_nights_val) * 100, 4)
            rai_data.append({
                "species": sp_name,
                "independent_events": events,
                "total_trap_nights": round(total_trap_nights_val, 2),
                "rai": rai_val,
            })

    return {
        "total_images": total_images,
        "processed_images": processed_images,
        "empty_images": empty_images,
        "total_detections": total_detections,
        "total_species": total_species,
        "quoll_detections": quoll_detections,
        "mean_detection_confidence": round(mean_det_conf, 4) if mean_det_conf else None,
        "mean_classification_confidence": round(mean_cls_conf, 4) if mean_cls_conf else None,
        "species_distribution": species_distribution,
        "camera_counts": camera_counts,
        "hourly_activity": hourly_activity,
        "monthly_activity": monthly_activity,
        "identified_quolls_over_time": identified_quolls_over_time,
        "recent_sightings": recent_sightings,
        "rai_data": rai_data,
        "total_trap_nights": round(total_trap_nights_val, 2),
    }


async def generate_batch_report(db: AsyncSession, job_id: int) -> dict | None:
    """Report for a specific batch processing job."""
    job = (await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))).scalar_one_or_none()
    if not job:
        return None

    elapsed = None
    if job.started_at and job.completed_at:
        elapsed = (job.completed_at - job.started_at).total_seconds()

    base_report = await generate_summary_report(db)
    base_report["job_id"] = job.id
    base_report["job_status"] = job.status
    base_report["processing_time_seconds"] = elapsed
    base_report["total_images"] = job.total_images
    base_report["processed_images"] = job.processed_images
    base_report["failed_images"] = job.failed_images
    return base_report


def export_report_csv(report: dict) -> str:
    """Convert report dict to CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["Metric", "Value"])
    for key in ["total_images", "processed_images", "empty_images", "total_detections",
                 "total_species", "quoll_detections", "mean_detection_confidence",
                 "mean_classification_confidence", "processing_time_seconds"]:
        writer.writerow([key, report.get(key, "")])

    writer.writerow([])
    writer.writerow(["Species", "Count"])
    for sp in report.get("species_distribution", []):
        writer.writerow([sp["species"], sp["count"]])

    writer.writerow([])
    writer.writerow(["Camera", "Detections"])
    for cam in report.get("camera_counts", []):
        writer.writerow([cam["camera"], cam["detections"]])

    writer.writerow([])
    writer.writerow(["Hour", "Detections"])
    for hr in report.get("hourly_activity", []):
        writer.writerow([hr["hour"], hr["detections"]])

    if report.get("rai_data"):
        writer.writerow([])
        writer.writerow(["Species", "Independent Events", "Trap-Nights", "RAI"])
        for entry in report["rai_data"]:
            writer.writerow([
                entry["species"], entry["independent_events"],
                entry["total_trap_nights"], entry["rai"],
            ])

    return buf.getvalue()


def export_report_json(report: dict) -> str:
    """Convert report dict to formatted JSON string."""
    return json.dumps(report, indent=2, default=str)
