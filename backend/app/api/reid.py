"""Re-identification prototype: static model summary for UI and demos."""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import reid_gallery_path, settings
from backend.app.db.session import get_db
from backend.app.models.detection import Detection
from backend.app.schemas.schemas import ReidSuggestionResponse, ReidSuggestionItem
from backend.app.services.reid_learning import log_reid_suggestions
from backend.app.utils.dependencies import get_current_user

router = APIRouter(prefix="/reid", tags=["Re-ID"])
logger = logging.getLogger(__name__)


def _default_info() -> dict:
    return {
        "model_name": "MegaDescriptor-L-384 (prototype)",
        "model_source": "https://huggingface.co/BVRA/MegaDescriptor-L-384",
        "summary": "See docs/REID_MODEL_RESULTS.md for full narrative.",
    }


@router.get("/info")
async def reid_model_info():
    """Return JSON summary for professor demo / frontend (no GPU required)."""
    path = settings.PROJECT_ROOT / "docs" / "reid_model_info.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = _default_info()
    else:
        data = _default_info()
    gp = reid_gallery_path()
    data = {**data, "runtime": {
        "gallery_path": str(gp),
        "gallery_exists": gp.is_file(),
        "auto_assign_enabled": bool(settings.REID_AUTO_ASSIGN and gp.is_file()),
        "sim_threshold": settings.REID_SIM_THRESHOLD,
        "gap_threshold": settings.REID_GAP_THRESHOLD,
    }}
    return data


@router.get("/detections/{detection_id}/suggestions", response_model=ReidSuggestionResponse)
async def reid_detection_suggestions(
    detection_id: int,
    top_k: int = Query(5, ge=1, le=10),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return top-k re-ID suggestions for a detection crop and log shown candidates."""
    det = await db.get(Detection, detection_id)
    if det is None:
        raise HTTPException(status_code=404, detail="Detection not found")
    if not det.crop_path:
        raise HTTPException(status_code=400, detail="Detection has no crop for re-ID")

    crop_abs = settings.STORAGE_ROOT / det.crop_path
    if not crop_abs.is_file():
        raise HTTPException(status_code=400, detail="Detection crop file not found")
    gallery = reid_gallery_path()
    if not gallery.is_file():
        raise HTTPException(status_code=400, detail=f"Re-ID gallery not found at {gallery}")

    try:
        from backend.worker.pipelines.megadescriptor_reid import predict_topk_crop

        result = await asyncio.to_thread(
            predict_topk_crop,
            crop_abs,
            gallery,
            settings.REID_SIM_THRESHOLD,
            settings.REID_GAP_THRESHOLD,
            top_k,
        )
    except Exception as exc:
        logger.exception("Failed generating re-ID suggestions for detection %s", detection_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate re-ID suggestions: {type(exc).__name__}",
        ) from exc

    if result is None:
        raise HTTPException(status_code=500, detail="Re-ID model unavailable")

    suggestions = list(result.get("suggestions", []))
    await log_reid_suggestions(db, detection_id, suggestions)

    top1 = suggestions[0] if suggestions else {}
    return ReidSuggestionResponse(
        detection_id=detection_id,
        suggestions=[
            ReidSuggestionItem(
                rank=int(item.get("rank", 0)),
                individual_id=str(item.get("individual_id", "")),
                similarity=float(item.get("similarity", 0.0)),
                confidence=float(item.get("confidence", 0.0)),
                accepted_by_gate=bool(item.get("accepted_by_gate", False)),
            )
            for item in suggestions
        ],
        gate_accepts_top1=bool(top1.get("accepted_by_gate", False)),
        sim_threshold=float(result.get("sim_threshold", settings.REID_SIM_THRESHOLD)),
        gap_threshold=float(result.get("gap_threshold", settings.REID_GAP_THRESHOLD)),
        gap=float(result.get("gap", 0.0)),
    )
