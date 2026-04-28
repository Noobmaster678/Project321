"""
MVP re-ID pipeline using frozen BVRA MegaDescriptor-L-384 (Hugging Face via timm).

- Filters identities by minimum image count (long-tail demo IDs).
- Optional quality gate: min short side + Laplacian blur variance (OpenCV).
- Builds per-class gallery as L2-normalized mean of train embeddings (prototype).
- Evaluates closed-set Rank-1 on held-out test images.
- Applies UNKNOWN rule: reject if top1_sim < sim_threshold OR (top1-top2) < gap_threshold.
- Optional --unknown-dir: images treated as out-of-gallery; reports reject vs false-ID rates.

Install: pip install timm
Model: https://huggingface.co/BVRA/MegaDescriptor-L-384

Example:
  python -m scripts.reid_megadescriptor_hf_mvp ^
    --root-dir "I:/AA-Study/Project321/dataset/IDed images/crops" ^
    --min-images-per-id 40 --test-ratio 0.2

Tune thresholds from validation scores, then:
  python -m scripts.reid_megadescriptor_hf_mvp --load-gallery storage/models/megadescriptor_l384_gallery.pt ^
    --unknown-dir "I:/path/to/other_quoll_crops"

Sweep sim/gap grid (one forward pass on test set):
  python -m scripts.reid_megadescriptor_hf_mvp --load-gallery storage/models/megadescriptor_l384_gallery.pt ^
    --sweep-thresholds --sim-grid "0.25,0.30,0.35,0.40" --gap-grid "0.02,0.03,0.05,0.07"
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import timm
except ImportError as e:
    raise ImportError(
        "reid_megadescriptor_hf_mvp requires timm. Install: pip install timm"
    ) from e


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".JPG", ".JPEG", ".PNG"}

MEGADESCRIPTOR_MODEL = "hf-hub:BVRA/MegaDescriptor-L-384"
IMAGE_SIZE = 384


def list_images(folder: Path) -> list[Path]:
    return sorted([p for p in folder.rglob("*") if p.is_file() and p.suffix in IMAGE_EXTS])


def list_id_folders(root: Path) -> list[Path]:
    return sorted([p for p in root.iterdir() if p.is_dir()])


def stable_shuffle(items: list, seed: int) -> list:
    rng = random.Random(seed)
    out = items[:]
    rng.shuffle(out)
    return out


def quality_ok(path: Path, min_short_side: int, blur_var_min: float) -> bool:
    """Drop tiny or very blurry crops. blur_var_min <= 0 disables blur check."""
    if min_short_side <= 0 and blur_var_min <= 0:
        return True
    if cv2 is None:
        if min_short_side > 0:
            with Image.open(path) as im:
                w, h = im.size
            return min(w, h) >= min_short_side
        return True
    img = cv2.imread(str(path))
    if img is None:
        return False
    h, w = img.shape[:2]
    if min_short_side > 0 and min(h, w) < min_short_side:
        return False
    if blur_var_min > 0:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if var < blur_var_min:
            return False
    return True


def filter_paths(paths: list[Path], min_short_side: int, blur_var_min: float) -> list[Path]:
    return [p for p in paths if quality_ok(p, min_short_side, blur_var_min)]


def split_per_id(
    id_to_paths: dict[str, list[Path]],
    test_ratio: float,
    seed: int,
) -> tuple[list[tuple[Path, int]], list[tuple[Path, int]], list[str]]:
    id_names = sorted(id_to_paths.keys())
    train: list[tuple[Path, int]] = []
    test: list[tuple[Path, int]] = []
    for cls_idx, qid in enumerate(id_names):
        paths = stable_shuffle(id_to_paths[qid], seed=seed + cls_idx * 997)
        if len(paths) < 4:
            raise ValueError(f"Need >=4 images for {qid} after filters, found {len(paths)}")
        n_test = max(1, int(len(paths) * test_ratio))
        n_test = min(n_test, len(paths) - 2)
        test_paths = paths[:n_test]
        train_paths = paths[n_test:]
        train.extend([(p, cls_idx) for p in train_paths])
        test.extend([(p, cls_idx) for p in test_paths])
    return train, test, id_names


class MegaDataset(Dataset):
    def __init__(self, items: list[tuple[Path, int]], train: bool):
        self.items = items
        if train:
            self.tf = transforms.Compose(
                [
                    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
                    transforms.RandomHorizontalFlip(p=0.5),
                    transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1),
                    transforms.ToTensor(),
                    transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
                ]
            )
        else:
            self.tf = transforms.Compose(
                [
                    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
                    transforms.ToTensor(),
                    transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
                ]
            )

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int, str]:
        p, y = self.items[idx]
        with Image.open(p) as img:
            img = img.convert("RGB")
            x = self.tf(img)
        return x, int(y), str(p)


@torch.no_grad()
def embed_batch(model: torch.nn.Module, x: torch.Tensor, device: str) -> torch.Tensor:
    z = model(x.to(device))
    if isinstance(z, (list, tuple)):
        z = z[0]
    return F.normalize(z.float(), p=2, dim=1).cpu()


def build_prototypes(
    model: torch.nn.Module,
    train_items: list[tuple[Path, int]],
    class_names: list[str],
    device: str,
    batch_size: int,
) -> torch.Tensor:
    """Mean embedding per class, L2-normalized -> [C, D]."""
    loader = DataLoader(
        MegaDataset(train_items, train=False),
        batch_size=min(batch_size, max(1, len(train_items))),
        shuffle=False,
        num_workers=0,
    )
    num_classes = len(class_names)
    sums: list[torch.Tensor] = [torch.zeros(1) for _ in range(num_classes)]
    counts = [0] * num_classes
    feat_dim: int | None = None

    model.eval()
    for x, y, _ in loader:
        z = embed_batch(model, x, device)
        if feat_dim is None:
            feat_dim = z.shape[1]
            sums = [torch.zeros(feat_dim) for _ in range(num_classes)]
        for i in range(z.shape[0]):
            c = int(y[i].item())
            sums[c] = sums[c] + z[i]
            counts[c] += 1

    protos = []
    for c in range(num_classes):
        if counts[c] == 0:
            raise RuntimeError(f"No train samples for class index {c}")
        v = sums[c] / counts[c]
        protos.append(F.normalize(v.unsqueeze(0), p=2, dim=1).squeeze(0))
    return torch.stack(protos, dim=0)


def predict_prototype(
    q: torch.Tensor,
    prototypes: torch.Tensor,
) -> tuple[int, float, float, int]:
    """Returns pred_idx, s1, s2, second_idx."""
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


@dataclass
class TestPredictions:
    """Per test image: true class, predicted top-1 class, top1_sim, top1-top2 gap."""

    true_y: np.ndarray
    pred_y: np.ndarray
    s1: np.ndarray
    gap: np.ndarray


def compute_test_predictions(
    model: torch.nn.Module,
    prototypes: torch.Tensor,
    test_items: list[tuple[Path, int]],
    device: str,
    batch_size: int,
) -> TestPredictions:
    loader = DataLoader(
        MegaDataset(test_items, train=False),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    model.eval()
    true_list: list[int] = []
    pred_list: list[int] = []
    s1_list: list[float] = []
    gap_list: list[float] = []

    with torch.no_grad():
        for x, y, _ in loader:
            z = embed_batch(model, x, device)
            for i in range(z.shape[0]):
                qi = z[i]
                pred_i, s1, s2, _ = predict_prototype(qi, prototypes)
                gap = s1 - s2 if s2 > -0.5 else s1
                true_list.append(int(y[i].item()))
                pred_list.append(pred_i)
                s1_list.append(s1)
                gap_list.append(gap)

    return TestPredictions(
        true_y=np.array(true_list, dtype=np.int64),
        pred_y=np.array(pred_list, dtype=np.int64),
        s1=np.array(s1_list, dtype=np.float64),
        gap=np.array(gap_list, dtype=np.float64),
    )


def print_threshold_sweep(
    pre: TestPredictions,
    sim_vals: Sequence[float],
    gap_vals: Sequence[float],
) -> None:
    """Print grid of UNKNOWN% / accept% / accuracy-on-accepted for each (sim_T, gap_T)."""
    n = len(pre.true_y)
    rank1 = float(np.mean(pre.pred_y == pre.true_y) * 100.0)

    print("=" * 100)
    print("Threshold sweep (UNKNOWN if top1_sim < sim_T OR gap < gap_T)")
    print(f"Test size: {n}  |  Rank-1 (no gate, always top-1): {rank1:.2f}%")
    print("=" * 100)
    header = (
        f"{'sim_T':>7} {'gap_T':>7} | {'UNK%':>7} {'acpt%':>7} "
        f"{'acc|ok':>8} | {'n_ok':>6} {'n_unk':>6}"
    )
    print(header)
    print("-" * 100)
    # acc% = acceptance rate; acc|ok = accuracy when accepted
    rows: list[tuple[float, float, float, float, float, int, int]] = []
    for sim_t in sim_vals:
        for gap_t in gap_vals:
            s1 = pre.s1
            g = pre.gap
            is_unk = (s1 < sim_t) | (g < gap_t)
            n_unk = int(np.sum(is_unk))
            n_ok = n - n_unk
            unk_pct = 100.0 * n_unk / max(1, n)
            acc_pct = 100.0 * n_ok / max(1, n)
            if n_ok > 0:
                acc_when = float(np.mean(pre.pred_y[~is_unk] == pre.true_y[~is_unk]) * 100.0)
            else:
                acc_when = float("nan")
            rows.append((sim_t, gap_t, unk_pct, acc_pct, acc_when, n_ok, n_unk))
            print(
                f"{sim_t:7.3f} {gap_t:7.3f} | {unk_pct:7.1f} {acc_pct:7.1f} "
                f"{acc_when:8.2f} | {n_ok:6d} {n_unk:6d}"
            )

    print("-" * 100)
    print("UNK%    = fraction predicted UNKNOWN")
    print("acpt%   = fraction accepted (not UNKNOWN)")
    print("acc|ok  = accuracy on accepted queries only")
    candidates = [r for r in rows if r[3] >= 30.0 and np.isfinite(r[4])]
    if candidates:
        best = max(candidates, key=lambda r: r[4])
        print(
            f"Heuristic pick (acc|ok max s.t. acpt% >= 30%): "
            f"sim_T={best[0]:.3f}, gap_T={best[1]:.3f} -> acc|ok={best[4]:.2f}%"
        )
    print("=" * 100)


def parse_float_csv(s: str) -> list[float]:
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def eval_closed_set(
    model: torch.nn.Module,
    prototypes: torch.Tensor,
    class_names: list[str],
    test_items: list[tuple[Path, int]],
    device: str,
    batch_size: int,
    sim_threshold: float,
    gap_threshold: float,
    precomputed: TestPredictions | None = None,
) -> None:
    if precomputed is None:
        precomputed = compute_test_predictions(model, prototypes, test_items, device, batch_size)

    pre = precomputed
    total = len(pre.true_y)
    correct = int(np.sum(pre.pred_y == pre.true_y))
    confusion = torch.zeros((len(class_names), len(class_names)), dtype=torch.int64)
    for t, p in zip(pre.true_y.tolist(), pre.pred_y.tolist()):
        confusion[int(t), int(p)] += 1

    unknown_count = int(np.sum((pre.s1 < sim_threshold) | (pre.gap < gap_threshold)))
    accept_mask = ~((pre.s1 < sim_threshold) | (pre.gap < gap_threshold))
    known_decisions = int(np.sum(accept_mask))
    correct_when_known = int(np.sum((pre.pred_y == pre.true_y) & accept_mask))

    acc = correct / max(1, total)
    print("=" * 60)
    print("Closed-set evaluation (argmax prototype vs true ID)")
    print("=" * 60)
    print(f"Test queries: {total}, Rank-1 correct: {correct}, acc: {acc*100:.2f}%")
    print("Confusion (rows=true, cols=pred) — always top-1 class:")
    print(confusion)

    print("=" * 60)
    print(f"UNKNOWN rule: top1_sim < {sim_threshold} OR gap < {gap_threshold}")
    print("=" * 60)
    print(f"Would predict UNKNOWN: {unknown_count}/{total} ({100*unknown_count/max(1,total):.1f}%)")
    if known_decisions > 0:
        ck = correct_when_known / known_decisions
        print(
            f"When accepting (not UNKNOWN): correct {correct_when_known}/{known_decisions} "
            f"({100*ck:.2f}%)"
        )
    if len(pre.s1):
        print(
            f"Score stats (top1_sim): min={float(np.min(pre.s1)):.4f} max={float(np.max(pre.s1)):.4f} "
            f"mean={float(np.mean(pre.s1)):.4f}"
        )
        print(
            f"Gap stats: min={float(np.min(pre.gap)):.4f} max={float(np.max(pre.gap)):.4f} "
            f"mean={float(np.mean(pre.gap)):.4f}"
        )


def run_single_query(
    model: torch.nn.Module,
    prototypes: torch.Tensor,
    class_names: list[str],
    query_path: Path,
    device: str,
    sim_threshold: float,
    gap_threshold: float,
) -> None:
    ds = MegaDataset([(query_path, 0)], train=False)
    x, _, _ = ds[0]
    z = embed_batch(model, x.unsqueeze(0), device)[0]
    pred_i, s1, s2, i2 = predict_prototype(z, prototypes)
    gap = s1 - s2 if s2 > -0.5 else s1
    is_unknown = (s1 < sim_threshold) or (gap < gap_threshold)
    print("=" * 60)
    print(f"Query: {query_path}")
    print(f"Decision: {'UNKNOWN' if is_unknown else class_names[pred_i]}")
    print(f"top1: {class_names[pred_i]} sim={s1:.4f}")
    if i2 >= 0:
        print(f"top2: {class_names[i2]} sim={s2:.4f}  gap={gap:.4f}")
    print(f"(thresholds: sim>={sim_threshold}, gap>={gap_threshold})")
    print("=" * 60)


def eval_unknown_dir(
    model: torch.nn.Module,
    prototypes: torch.Tensor,
    class_names: list[str],
    unknown_dir: Path,
    device: str,
    batch_size: int,
    sim_threshold: float,
    gap_threshold: float,
    min_short_side: int,
    blur_var_min: float,
) -> None:
    paths = filter_paths(list_images(unknown_dir), min_short_side, blur_var_min)
    if not paths:
        print(f"No images in unknown dir after filters: {unknown_dir}")
        return
    loader = DataLoader(
        MegaDataset([(p, 0) for p in paths], train=False),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    model.eval()
    rejected = 0
    accepted_wrong = 0
    with torch.no_grad():
        for x, _, _ in loader:
            z = embed_batch(model, x, device)
            for i in range(z.shape[0]):
                pred_i, s1, s2, _ = predict_prototype(z[i], prototypes)
                gap = s1 - s2 if s2 > -0.5 else s1
                is_unknown = (s1 < sim_threshold) or (gap < gap_threshold)
                if is_unknown:
                    rejected += 1
                else:
                    accepted_wrong += 1
    n = len(paths)
    print("=" * 60)
    print(f"Unknown / OOD folder: {unknown_dir}")
    print("=" * 60)
    print(f"Images: {n}")
    print(
        f"UNKNOWN (reject): {rejected}/{n} ({100*rejected/max(1,n):.1f}%) "
        f"— want this high for true unknowns"
    )
    print(
        f"Assigned a known ID: {accepted_wrong}/{n} ({100*accepted_wrong/max(1,n):.1f}%) "
        f"— want this low for demo"
    )


@dataclass
class Config:
    root_dir: Path
    min_images_per_id: int
    test_ratio: float
    seed: int
    batch_size: int
    min_short_side: int
    blur_var_min: float
    sim_threshold: float
    gap_threshold: float
    output: Path
    unknown_dir: Path | None
    load_gallery: Path | None
    query_image: Path | None
    sweep_thresholds: bool
    sim_grid: list[float]
    gap_grid: list[float]
    sweep_skip_eval: bool


def collect_dataset(cfg: Config) -> dict[str, list[Path]]:
    id_folders = list_id_folders(cfg.root_dir)
    id_to_paths: dict[str, list[Path]] = {}
    skipped: list[tuple[str, int]] = []
    for d in id_folders:
        raw = list_images(d)
        paths = filter_paths(raw, cfg.min_short_side, cfg.blur_var_min)
        if len(paths) < cfg.min_images_per_id:
            skipped.append((d.name, len(paths)))
            continue
        id_to_paths[d.name] = paths
    if not id_to_paths:
        raise ValueError(
            "No identities left after --min-images-per-id and quality filters. "
            "Lower --min-images-per-id or relax blur/size thresholds."
        )
    print(f"Using {len(id_to_paths)} identities (min_images>={cfg.min_images_per_id}):")
    for k in sorted(id_to_paths.keys()):
        print(f"  {k}: {len(id_to_paths[k])} crops")
    if skipped:
        print(f"Skipped {len(skipped)} folders below min count or empty after quality filter.")
    return id_to_paths


def run(cfg: Config) -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    print(f"Loading frozen model: {MEGADESCRIPTOR_MODEL}")

    model = timm.create_model(MEGADESCRIPTOR_MODEL, pretrained=True)
    model.eval()
    for p in model.parameters():
        p.requires_grad = False
    model = model.to(device)

    prototypes: torch.Tensor
    class_names: list[str]
    test_items: list[tuple[Path, int]] | None = None

    if cfg.load_gallery and cfg.load_gallery.exists():
        ckpt = torch.load(cfg.load_gallery, map_location="cpu")
        prototypes = ckpt["prototypes"]
        class_names = list(ckpt["class_names"])
        print(f"Loaded gallery from {cfg.load_gallery} ({len(class_names)} classes)")
        if cfg.root_dir.exists():
            id_to_paths = collect_dataset(cfg)
            _, test_items, cn2 = split_per_id(id_to_paths, cfg.test_ratio, cfg.seed)
            if cn2 != class_names:
                print(
                    "WARNING: dataset class list differs from checkpoint (IDs or order). "
                    "Eval numbers may not match the saved gallery."
                )
    else:
        if not cfg.root_dir.exists():
            raise FileNotFoundError(cfg.root_dir)
        id_to_paths = collect_dataset(cfg)
        train_items, test_items, class_names = split_per_id(id_to_paths, cfg.test_ratio, cfg.seed)
        print(f"Train samples: {len(train_items)}, test samples: {len(test_items)}")
        prototypes = build_prototypes(model, train_items, class_names, device, cfg.batch_size)
        cfg.output.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "prototypes": prototypes,
                "class_names": class_names,
                "model": MEGADESCRIPTOR_MODEL,
                "image_size": IMAGE_SIZE,
                "normalize": "0.5",
                "min_images_per_id": cfg.min_images_per_id,
                "sim_threshold": cfg.sim_threshold,
                "gap_threshold": cfg.gap_threshold,
            },
            cfg.output,
        )
        print(f"Saved gallery checkpoint: {cfg.output}")

    if cfg.sweep_thresholds and test_items is None:
        print(
            "WARNING: --sweep-thresholds skipped: need test images. "
            "Use --root-dir pointing at your crop folder (same run as building gallery, "
            "or with --load-gallery and an existing --root-dir)."
        )

    if test_items is not None:
        precomputed: TestPredictions | None = None
        if cfg.sweep_thresholds:
            if not cfg.sim_grid or not cfg.gap_grid:
                raise ValueError("--sim-grid and --gap-grid must each list at least one number")
            precomputed = compute_test_predictions(
                model, prototypes, test_items, device, cfg.batch_size
            )
            print_threshold_sweep(precomputed, cfg.sim_grid, cfg.gap_grid)
        if not cfg.sweep_skip_eval:
            eval_closed_set(
                model,
                prototypes,
                class_names,
                test_items,
                device,
                cfg.batch_size,
                cfg.sim_threshold,
                cfg.gap_threshold,
                precomputed=precomputed,
            )

    if cfg.unknown_dir and cfg.unknown_dir.exists():
        ckpt_path = cfg.load_gallery if (cfg.load_gallery and cfg.load_gallery.exists()) else cfg.output
        if not Path(ckpt_path).exists():
            raise FileNotFoundError(f"Need gallery at {ckpt_path} for --unknown-dir eval")
        ckpt = torch.load(ckpt_path, map_location="cpu")
        protos = ckpt["prototypes"]
        cnames = list(ckpt["class_names"])
        eval_unknown_dir(
            model,
            protos,
            cnames,
            cfg.unknown_dir,
            device,
            cfg.batch_size,
            cfg.sim_threshold,
            cfg.gap_threshold,
            cfg.min_short_side,
            cfg.blur_var_min,
        )

    if cfg.query_image and cfg.query_image.exists():
        ckpt_path = cfg.load_gallery if (cfg.load_gallery and cfg.load_gallery.exists()) else cfg.output
        if not Path(ckpt_path).exists():
            raise FileNotFoundError(f"Need gallery at {ckpt_path} for --query")
        ckpt = torch.load(ckpt_path, map_location="cpu")
        protos = ckpt["prototypes"]
        cnames = list(ckpt["class_names"])
        run_single_query(
            model,
            protos,
            cnames,
            cfg.query_image,
            device,
            cfg.sim_threshold,
            cfg.gap_threshold,
        )


def main() -> None:
    p = argparse.ArgumentParser(description="Frozen MegaDescriptor-L-384 re-ID MVP")
    p.add_argument(
        "--root-dir",
        type=Path,
        default=Path(r"I:/AA-Study/Project321/dataset/IDed images/crops"),
        help="Parent folder containing one subfolder per quoll ID",
    )
    p.add_argument("--min-images-per-id", type=int, default=40, help="Skip IDs with fewer crops")
    p.add_argument("--test-ratio", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--batch-size", type=int, default=8, help="Lower if OOM on 384px Swin-L")
    p.add_argument("--min-short-side", type=int, default=64, help="0 to disable")
    p.add_argument(
        "--blur-var-min",
        type=float,
        default=30.0,
        help="Laplacian variance threshold; lower = keep more; 0 = off",
    )
    p.add_argument(
        "--sim-threshold",
        type=float,
        default=0.35,
        help="Below this top1 cosine to best prototype => UNKNOWN",
    )
    p.add_argument(
        "--gap-threshold",
        type=float,
        default=0.05,
        help="Below (top1-top2) gap => UNKNOWN",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("storage/models/megadescriptor_l384_gallery.pt"),
    )
    p.add_argument(
        "--unknown-dir",
        type=Path,
        default=None,
        help="Folder of crops not in gallery; measure UNKNOWN vs false-ID",
    )
    p.add_argument(
        "--load-gallery",
        type=Path,
        default=None,
        help="Skip training build; load prototypes from this file",
    )
    p.add_argument(
        "--query",
        type=Path,
        default=None,
        help="Single crop path: print UNKNOWN vs best ID (needs saved gallery)",
    )
    p.add_argument(
        "--sweep-thresholds",
        action="store_true",
        help="Print grid of sim_T x gap_T vs UNK%% / accept%% / acc-on-accepted (one test forward pass)",
    )
    p.add_argument(
        "--sim-grid",
        type=str,
        default="0.20,0.25,0.30,0.35,0.40,0.45",
        help="Comma-separated sim_T values for --sweep-thresholds",
    )
    p.add_argument(
        "--gap-grid",
        type=str,
        default="0.01,0.02,0.03,0.05,0.07,0.10",
        help="Comma-separated gap_T values for --sweep-thresholds",
    )
    p.add_argument(
        "--sweep-skip-eval",
        action="store_true",
        help="With --sweep-thresholds, only print the grid (skip confusion matrix / single-threshold block)",
    )
    args = p.parse_args()

    cfg = Config(
        root_dir=args.root_dir,
        min_images_per_id=args.min_images_per_id,
        test_ratio=args.test_ratio,
        seed=args.seed,
        batch_size=args.batch_size,
        min_short_side=args.min_short_side,
        blur_var_min=args.blur_var_min,
        sim_threshold=args.sim_threshold,
        gap_threshold=args.gap_threshold,
        output=args.output,
        unknown_dir=args.unknown_dir,
        load_gallery=args.load_gallery,
        query_image=args.query,
        sweep_thresholds=args.sweep_thresholds,
        sim_grid=parse_float_csv(args.sim_grid),
        gap_grid=parse_float_csv(args.gap_grid),
        sweep_skip_eval=args.sweep_skip_eval,
    )
    run(cfg)


if __name__ == "__main__":
    main()
