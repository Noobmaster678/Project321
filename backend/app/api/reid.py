"""Re-identification prototype: static model summary for UI and demos."""
import json

from fastapi import APIRouter

from backend.app.config import reid_gallery_path, settings

router = APIRouter(prefix="/reid", tags=["Re-ID"])


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
