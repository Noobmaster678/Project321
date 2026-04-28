"""
MegaDescriptor-L-384 + saved prototype gallery for automatic quoll re-ID on crops.

Gallery format matches scripts/reid_megadescriptor_hf_mvp.py (torch.save with
prototypes, class_names). Lazy-loaded once per gallery path.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)

MEGADESCRIPTOR_MODEL = "hf-hub:BVRA/MegaDescriptor-L-384"
IMAGE_SIZE = 384

_state: dict[str, Any] | None = None


def _eval_transform():
    return transforms.Compose(
        [
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
        ]
    )


@torch.no_grad()
def _embed_one(model: torch.nn.Module, x: torch.Tensor, device: str) -> torch.Tensor:
    z = model(x.to(device))
    if isinstance(z, (list, tuple)):
        z = z[0]
    return F.normalize(z.float(), p=2, dim=1).cpu()


def _predict_prototype(
    q: torch.Tensor, prototypes: torch.Tensor
) -> tuple[int, float, float, int]:
    """q: [D], prototypes: [C, D] — cosine sims = dot product when normalized."""
    sims = q @ prototypes.T
    top2_vals, top2_idx = torch.topk(sims, k=min(2, sims.numel()))
    s1 = float(top2_vals[0].item())
    if top2_vals.numel() > 1:
        s2 = float(top2_vals[1].item())
        i2 = int(top2_idx[1].item())
    else:
        s2 = -1.0
        i2 = -1
    i1 = int(top2_idx[0].item())
    return i1, s1, s2, i2


def _ensure_state(gallery_path: Path) -> dict[str, Any] | None:
    global _state
    path_res = gallery_path.resolve()
    if not path_res.is_file():
        return None
    if _state is not None and _state.get("path") == str(path_res):
        return _state
    try:
        import timm
    except ImportError as e:
        logger.warning("megadescriptor_reid: timm not available (%s)", e)
        return None
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            ckpt = torch.load(path_res, map_location="cpu", weights_only=False)
        except TypeError:
            ckpt = torch.load(path_res, map_location="cpu")
        prototypes = ckpt["prototypes"].float().cpu()
        class_names = [str(x) for x in ckpt["class_names"]]
        model = timm.create_model(MEGADESCRIPTOR_MODEL, pretrained=True)
        model.eval()
        for p in model.parameters():
            p.requires_grad = False
        model = model.to(device)
        _state = {
            "path": str(path_res),
            "model": model,
            "device": device,
            "prototypes": prototypes,
            "class_names": class_names,
            "tf": _eval_transform(),
        }
        logger.info("megadescriptor_reid: loaded gallery %s (%d IDs)", path_res, len(class_names))
        return _state
    except Exception:
        logger.exception("megadescriptor_reid: failed to load gallery %s", path_res)
        return None


def predict_crop(
    crop_abs_path: Path,
    gallery_path: Path,
    sim_threshold: float,
    gap_threshold: float,
) -> tuple[str | None, dict[str, float]]:
    """
    Returns (individual_id, meta) if the UNKNOWN gate accepts; otherwise (None, meta).
    """
    st = _ensure_state(gallery_path)
    if st is None:
        return None, {}
    path = crop_abs_path.resolve()
    if not path.is_file():
        return None, {}
    try:
        with Image.open(path) as im:
            rgb = im.convert("RGB")
            x = st["tf"](rgb).unsqueeze(0)
    except Exception:
        logger.warning("megadescriptor_reid: could not read crop %s", path)
        return None, {}

    model = st["model"]
    device = st["device"]
    protos = st["prototypes"]
    names = st["class_names"]

    z = _embed_one(model, x, device).squeeze(0)
    pred_i, s1, s2, _i2 = _predict_prototype(z, protos)
    gap = s1 - s2 if s2 > -0.5 else s1
    meta = {"s1": s1, "s2": s2, "gap": gap, "pred_idx": float(pred_i)}

    if s1 < sim_threshold or gap < gap_threshold:
        return None, meta
    if pred_i < 0 or pred_i >= len(names):
        return None, meta
    return names[pred_i], meta
