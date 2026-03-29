"""
Crop IDed Quoll Images for Re-ID Training
==========================================
Runs MegaDetector + AWC135 on the organized IDed images to produce
high-quality quoll crops suitable for training a re-ID model.

Only keeps crops where:
  - MegaDetector detection confidence >= --det-thresh  (default 0.5)
  - AWC135 classifies the crop as quoll with confidence >= --cls-thresh (default 0.5)
  - Crop is at least --min-size pixels on its shortest side (default 100)

Output:
    dataset/IDed images/crops/{quoll_id}/{source_image}_{det_index}.jpg

Usage (from project root, in the 'wildlife' conda env):
    python -m scripts.crop_ided_images --dry-run
    python -m scripts.crop_ided_images
    python -m scripts.crop_ided_images --det-thresh 0.6 --cls-thresh 0.7 --min-size 128
    python -m scripts.crop_ided_images --quoll 02Q2   # process a single quoll
"""
import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image

from backend.app.config import settings
from backend.worker.pipelines.megadetector_pipeline import MegaDetectorPipeline
from backend.worker.pipelines.awc135_pipeline import AWC135Pipeline

IDED_DIR = settings.DATASET_ROOT / "IDed images"
CROPS_DIR = IDED_DIR / "crops"


def get_crop_dimensions(image_path: Path, bbox: list[float], padding: float = 0.05):
    """Calculate crop pixel dimensions without actually cropping."""
    with Image.open(image_path) as img:
        w_img, h_img = img.size

    x, y, w, h = bbox
    pad_x, pad_y = w * padding, h * padding
    x1 = max(0, int((x - pad_x) * w_img))
    y1 = max(0, int((y - pad_y) * h_img))
    x2 = min(w_img, int((x + w + pad_x) * w_img))
    y2 = min(h_img, int((y + h + pad_y) * h_img))
    return x2 - x1, y2 - y1


def run_cropping(
    det_thresh: float = 0.5,
    cls_thresh: float = 0.5,
    min_size: int = 100,
    quoll_filter: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
):
    print("=" * 60)
    print("Crop IDed Quoll Images for Re-ID")
    print("=" * 60)
    print(f"  Detection threshold:      {det_thresh}")
    print(f"  Classification threshold: {cls_thresh}")
    print(f"  Min crop size:            {min_size}px")
    if quoll_filter:
        print(f"  Processing quoll:         {quoll_filter}")
    print()

    if not IDED_DIR.exists():
        raise FileNotFoundError(f"IDed images dir not found: {IDED_DIR}")

    quoll_dirs = sorted([
        d for d in IDED_DIR.iterdir()
        if d.is_dir() and d.name != "crops"
        and (quoll_filter is None or d.name == quoll_filter)
    ])
    print(f"Found {len(quoll_dirs)} quoll folders")

    total_images = sum(
        len({p.name: p for p in list(d.glob("*.JPG")) + list(d.glob("*.jpg"))})
        for d in quoll_dirs
    )
    print(f"Total images to process: {total_images}")
    print()

    # Load models
    print("Loading models...")
    md = MegaDetectorPipeline()
    md.confidence_threshold = det_thresh
    awc = AWC135Pipeline()
    awc.confidence_threshold = cls_thresh

    t0 = time.time()
    md.load_model()
    print(f"  MegaDetector ready ({time.time() - t0:.1f}s)")

    t0 = time.time()
    awc.load_model()
    print(f"  AWC135 ready       ({time.time() - t0:.1f}s)")
    print()

    stats = {
        "images_processed": 0,
        "no_detection": 0,
        "crops_saved": 0,
        "rejected_not_quoll": 0,
        "rejected_low_det_conf": 0,
        "rejected_too_small": 0,
        "errors": 0,
    }
    per_quoll: dict[str, int] = defaultdict(int)
    pipeline_start = time.time()

    for quoll_dir in quoll_dirs:
        qid = quoll_dir.name
        images = sorted({p.name: p for p in
            list(quoll_dir.glob("*.JPG")) + list(quoll_dir.glob("*.jpg"))
        }.values())
        if not images:
            continue

        crop_out = CROPS_DIR / qid
        if not dry_run:
            crop_out.mkdir(parents=True, exist_ok=True)

        for img_path in images:
            stats["images_processed"] += 1
            stem = img_path.stem

            if stats["images_processed"] % 200 == 0:
                elapsed = time.time() - pipeline_start
                rate = stats["images_processed"] / elapsed if elapsed > 0 else 0
                print(
                    f"  [{stats['images_processed']}/{total_images}] "
                    f"{rate:.1f} img/s | "
                    f"{stats['crops_saved']} crops saved"
                )

            try:
                detections = md.detect_single(img_path)
                animal_dets = [d for d in detections if d["category"] == "animal"]

                if not animal_dets:
                    stats["no_detection"] += 1
                    if verbose:
                        print(f"    [skip] {img_path.name} — no animal detected")
                    continue

                for i, det in enumerate(animal_dets):
                    det_conf = det["confidence"]
                    if det_conf < det_thresh:
                        stats["rejected_low_det_conf"] += 1
                        continue

                    crop_w, crop_h = get_crop_dimensions(img_path, det["bbox"])
                    if min(crop_w, crop_h) < min_size:
                        stats["rejected_too_small"] += 1
                        if verbose:
                            print(f"    [small] {img_path.name} det{i} — {crop_w}x{crop_h}")
                        continue

                    cls = awc.classify_single(
                        img_path, bbox=det["bbox"], bbox_conf=det_conf,
                    )
                    species = cls.get("species") or ""
                    cls_conf = cls.get("confidence", 0.0)
                    is_quoll = "quoll" in species.lower() and cls_conf >= cls_thresh

                    if not is_quoll:
                        stats["rejected_not_quoll"] += 1
                        if verbose:
                            print(
                                f"    [!quoll] {img_path.name} det{i} — "
                                f"{species} ({cls_conf:.2f})"
                            )
                        continue

                    crop_name = f"{stem}_{i}.jpg"
                    crop_path = crop_out / crop_name

                    if not dry_run:
                        md.crop_detection(img_path, det["bbox"], crop_path)

                    stats["crops_saved"] += 1
                    per_quoll[qid] += 1

                    if verbose:
                        print(
                            f"    [CROP] {img_path.name} det{i} — "
                            f"det={det_conf:.2f} cls={cls_conf:.2f} "
                            f"{crop_w}x{crop_h}"
                        )

            except Exception as e:
                stats["errors"] += 1
                if verbose:
                    print(f"    [ERROR] {img_path.name}: {e}")

    elapsed = time.time() - pipeline_start
    rate = stats["images_processed"] / elapsed if elapsed > 0 else 0

    print()
    print("=" * 60)
    tag = "[DRY RUN] " if dry_run else ""
    print(f"{tag}Results ({elapsed:.0f}s, {rate:.1f} img/s)")
    print(f"  Images processed:        {stats['images_processed']}")
    print(f"  No animal detected:      {stats['no_detection']}")
    print(f"  Rejected (not quoll):    {stats['rejected_not_quoll']}")
    print(f"  Rejected (low det conf): {stats['rejected_low_det_conf']}")
    print(f"  Rejected (too small):    {stats['rejected_too_small']}")
    print(f"  Errors:                  {stats['errors']}")
    print(f"  Crops saved:             {stats['crops_saved']}")
    print()
    print("Per-quoll crops:")
    for qid in sorted(per_quoll.keys()):
        print(f"  {qid}: {per_quoll[qid]} crops")
    print(f"  Total quoll IDs with crops: {len(per_quoll)}")
    print("=" * 60)

    summary_path = CROPS_DIR / "crop_summary.json"
    summary = {
        "thresholds": {
            "detection": det_thresh,
            "classification": cls_thresh,
            "min_crop_size": min_size,
        },
        "stats": stats,
        "per_quoll": dict(sorted(per_quoll.items())),
    }
    if not dry_run:
        CROPS_DIR.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crop IDed quoll images for re-ID training")
    parser.add_argument("--det-thresh", type=float, default=0.5,
                        help="MegaDetector min confidence (default: 0.5)")
    parser.add_argument("--cls-thresh", type=float, default=0.5,
                        help="AWC135 min quoll confidence (default: 0.5)")
    parser.add_argument("--min-size", type=int, default=100,
                        help="Min crop short-side pixels (default: 100)")
    parser.add_argument("--quoll", type=str, default=None,
                        help="Process a single quoll ID only (e.g. 02Q2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be done without saving crops")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print per-detection details")
    args = parser.parse_args()

    run_cropping(
        det_thresh=args.det_thresh,
        cls_thresh=args.cls_thresh,
        min_size=args.min_size,
        quoll_filter=args.quoll,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
