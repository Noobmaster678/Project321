"""
MegaDescriptor-L-384 + saved prototype gallery for automatic quoll re-ID on crops.

Gallery format matches scripts/reid_megadescriptor_hf_mvp.py (torch.save with
prototypes, class_names). Lazy-loaded once per gallery path.
"""
from __future__ import annotations

import fcntl
import logging
import os
from pathlib import Path
import tempfile
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


def _score_confidence(s1: float, gap: float, sim_threshold: float, gap_threshold: float) -> float:
    """Heuristic confidence score normalized to [0,1] around gate thresholds."""
    sim_span = max(1e-6, 1.0 - sim_threshold)
    gap_span = max(1e-6, 1.0 - gap_threshold)
    sim_norm = max(0.0, min((s1 - sim_threshold) / sim_span, 1.0))
    gap_norm = max(0.0, min((gap - gap_threshold) / gap_span, 1.0))
    return max(0.0, min(0.7 * sim_norm + 0.3 * gap_norm, 1.0))


def _ensure_state(gallery_path: Path) -> dict[str, Any] | None:
    global _state
    path_res = gallery_path.resolve()
    if not path_res.is_file():
        return None
    stat = path_res.stat()
    mtime_ns = int(stat.st_mtime_ns)
    size = int(stat.st_size)
    if (
        _state is not None
        and _state.get("path") == str(path_res)
        and _state.get("mtime_ns") == mtime_ns
        and _state.get("size") == size
    ):
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
        prototype_counts = ckpt.get("prototype_counts")
        if not isinstance(prototype_counts, list) or len(prototype_counts) != len(class_names):
            prototype_counts = [1 for _ in class_names]
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
            "prototype_counts": prototype_counts,
            "tf": _eval_transform(),
            "mtime_ns": mtime_ns,
            "size": size,
            "gallery_version": int(ckpt.get("gallery_version", 1)),
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

    topk = predict_topk_crop(
        path,
        gallery_path,
        sim_threshold=sim_threshold,
        gap_threshold=gap_threshold,
        top_k=5,
    )
    if topk is None:
        return None, {}
    suggestions = topk.get("suggestions", [])
    if not suggestions:
        return None, {}
    best = suggestions[0]
    if not bool(best.get("accepted_by_gate", False)):
        return None, {}
    meta = {
        "s1": float(best.get("similarity", 0.0)),
        "s2": float(topk.get("second_similarity", -1.0)),
        "gap": float(topk.get("gap", 0.0)),
        "pred_idx": float(best.get("pred_idx", -1)),
        "confidence": float(best.get("confidence", 0.0)),
    }
    individual_id = best.get("individual_id")
    return (str(individual_id), meta) if individual_id else (None, meta)


def predict_topk_crop(
    crop_abs_path: Path,
    gallery_path: Path,
    sim_threshold: float,
    gap_threshold: float,
    top_k: int = 5,
) -> dict[str, Any] | None:
    """Return ranked top-k re-ID suggestions for a crop."""
    st = _ensure_state(gallery_path)
    if st is None:
        return None
    path = crop_abs_path.resolve()
    if not path.is_file():
        return None
    try:
        with Image.open(path) as im:
            rgb = im.convert("RGB")
            x = st["tf"](rgb).unsqueeze(0)
    except Exception:
        logger.warning("megadescriptor_reid: could not read crop %s", path)
        return None

    model = st["model"]
    device = st["device"]
    protos: torch.Tensor = st["prototypes"]
    names: list[str] = st["class_names"]

    z = _embed_one(model, x, device).squeeze(0)
    sims = z @ protos.T
    k = max(1, min(int(top_k), int(sims.numel())))
    vals, idxs = torch.topk(sims, k=k)
    s1 = float(vals[0].item())
    s2 = float(vals[1].item()) if vals.numel() > 1 else -1.0
    gap = s1 - s2 if s2 > -0.5 else s1

    suggestions: list[dict[str, Any]] = []
    for rank, (value, idx) in enumerate(zip(vals.tolist(), idxs.tolist()), start=1):
        pred_idx = int(idx)
        if pred_idx < 0 or pred_idx >= len(names):
            continue
        sim = float(value)
        accepted = bool(rank == 1 and sim >= sim_threshold and gap >= gap_threshold)
        suggestions.append(
            {
                "rank": rank,
                "pred_idx": pred_idx,
                "individual_id": names[pred_idx],
                "similarity": sim,
                "confidence": _score_confidence(sim if rank == 1 else sim, gap if rank == 1 else 0.0, sim_threshold, gap_threshold),
                "accepted_by_gate": accepted,
            }
        )

    return {
        "suggestions": suggestions,
        "s1": s1,
        "second_similarity": s2,
        "gap": gap,
        "sim_threshold": sim_threshold,
        "gap_threshold": gap_threshold,
    }


def embed_crop(crop_abs_path: Path, gallery_path: Path) -> torch.Tensor | None:
    """Embed a crop using the loaded MegaDescriptor state."""
    st = _ensure_state(gallery_path)
    if st is None:
        return None
    path = crop_abs_path.resolve()
    if not path.is_file():
        return None
    try:
        with Image.open(path) as im:
            rgb = im.convert("RGB")
            x = st["tf"](rgb).unsqueeze(0)
    except Exception:
        return None
    return _embed_one(st["model"], x, st["device"]).squeeze(0)


def incremental_update_gallery(gallery_path: Path, individual_id: str, embedding: torch.Tensor) -> bool:
    """Atomically update or append an individual's prototype in the saved gallery."""
    global _state

    lock_path = gallery_path.with_name(f".{gallery_path.name}.lock")
    try:
        lock_file = lock_path.open("a+b")
    except OSError:
        logger.exception("megadescriptor_reid: could not open gallery lock %s", lock_path)
        return False

    with lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        # Reload after taking the inter-process lock so this update includes any
        # checkpoint written by another API or worker process while we waited.
        st = _ensure_state(gallery_path)
        if st is None:
            return False

        # Build a new snapshot instead of mutating the cached objects that
        # concurrent inference requests may still be reading.
        names: list[str] = list(st["class_names"])
        protos: torch.Tensor = st["prototypes"].clone()
        emb = F.normalize(embedding.float().view(1, -1), p=2, dim=1).cpu().squeeze(0)
        stored_counts = st.get("prototype_counts")
        if isinstance(stored_counts, list) and len(stored_counts) == len(names):
            counts = list(stored_counts)
        else:
            counts = [1 for _ in names]

        if individual_id in names:
            idx = names.index(individual_id)
            n = max(1, int(counts[idx]))
            protos[idx] = F.normalize((protos[idx] * n) + emb, p=2, dim=0)
            counts[idx] = n + 1
        else:
            names.append(individual_id)
            protos = torch.cat([protos, emb.unsqueeze(0)], dim=0)
            counts.append(1)

        ckpt = {
            "prototypes": protos.cpu(),
            "class_names": names,
            "prototype_counts": counts,
            "gallery_version": int(st.get("gallery_version", 1)) + 1,
        }

        tmp_path: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                dir=gallery_path.parent,
                prefix=f".{gallery_path.name}.",
                suffix=".tmp",
            )
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "wb") as tmp_file:
                torch.save(ckpt, tmp_file)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            tmp_path.replace(gallery_path)
        except OSError:
            logger.exception("megadescriptor_reid: failed writing gallery %s", gallery_path)
            return False
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        try:
            stat = gallery_path.stat()
            mtime_ns = int(stat.st_mtime_ns)
            size = int(stat.st_size)
        except OSError:
            mtime_ns = st.get("mtime_ns")
            size = st.get("size")

        _state = {
            **st,
            "prototypes": protos.cpu(),
            "class_names": names,
            "prototype_counts": counts,
            "gallery_version": ckpt["gallery_version"],
            "mtime_ns": mtime_ns,
            "size": size,
        }
        return True
