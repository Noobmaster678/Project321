"""
Organize IDed Quoll Images
===========================
Reads stq-morton-data-cleaned.csv and copies identified quoll images from
MORTON NP PHOTOS into dataset/IDed images/{individual_id}/ folders, ready
for the detection/cropping pipeline.

Usage (from project root):
    python -m scripts.organize_ided_images --dry-run
    python -m scripts.organize_ided_images
"""
import argparse
import re
import shutil
from collections import defaultdict
from pathlib import Path

import pandas as pd

DATASET_ROOT = Path(__file__).resolve().parent.parent / "dataset"
PHOTOS_DIR = DATASET_ROOT / "MORTON NP PHOTOS"
CSV_PATH = DATASET_ROOT / "stq-morton-data-cleaned.csv"
OUTPUT_DIR = DATASET_ROOT / "IDed images"


def build_camera_folder_lookup(photos_dir: Path) -> dict[str, dict[int, list[Path]]]:
    """
    Build a mapping: collection_folder_name -> {camera_number: [folder_paths]}.
    Camera folders follow patterns like '2A_12-10-23', '4A-12-10-23'.
    """
    pattern = re.compile(r"^(\d+)[AB][-_]")
    lookup: dict[str, dict[int, list[Path]]] = {}

    for coll_dir in sorted(photos_dir.iterdir()):
        if not coll_dir.is_dir() or not coll_dir.name.startswith("Collection-"):
            continue
        cam_map: dict[int, list[Path]] = defaultdict(list)
        for cam_dir in coll_dir.iterdir():
            if not cam_dir.is_dir():
                continue
            m = pattern.match(cam_dir.name)
            if m:
                cam_map[int(m.group(1))].append(cam_dir)
        lookup[coll_dir.name] = dict(cam_map)

    return lookup


def resolve_source_path(
    filename: str,
    camera_id: int,
    collection_id: str,
    cam_lookup: dict[str, dict[int, list[Path]]],
    file_index: dict[str, Path] | None = None,
) -> Path | None:
    """Find the actual file path inside MORTON NP PHOTOS.

    Checks the camera folder directly first, then any subdirectories
    (e.g. 100RECNX/, 101RECNX/) that some cameras use.
    If a pre-built file_index is provided, uses that for O(1) lookups.
    """
    if file_index is not None:
        key = f"{collection_id}/{camera_id}/{filename}"
        return file_index.get(key)

    coll_cams = cam_lookup.get(collection_id)
    if not coll_cams:
        return None

    cam_folders = coll_cams.get(camera_id, [])
    for cam_folder in cam_folders:
        candidate = cam_folder / filename
        if candidate.exists():
            return candidate
        for sub in cam_folder.iterdir():
            if sub.is_dir():
                candidate = sub / filename
                if candidate.exists():
                    return candidate

    return None


def organize_images(dry_run: bool = False) -> None:
    print("=" * 60)
    print("Organize IDed Quoll Images for Re-ID")
    print("=" * 60)

    if not PHOTOS_DIR.exists():
        raise FileNotFoundError(f"Photos directory not found: {PHOTOS_DIR}")
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)
    print(f"CSV loaded: {len(df)} rows, {df['individual_id'].nunique()} unique quolls")

    print("Building camera folder lookup...")
    cam_lookup = build_camera_folder_lookup(PHOTOS_DIR)
    total_cam_folders = sum(
        len(folders) for coll in cam_lookup.values() for folders in coll.values()
    )
    print(f"  {len(cam_lookup)} collections, {total_cam_folders} camera folders indexed")

    print("Indexing files (including subdirectories like 100RECNX/)...")
    file_index: dict[str, Path] = {}
    for coll_name, cam_map in cam_lookup.items():
        for cam_num, folders in cam_map.items():
            for cam_folder in folders:
                for img in cam_folder.rglob("*.JPG"):
                    file_index[f"{coll_name}/{cam_num}/{img.name}"] = img
                for img in cam_folder.rglob("*.jpg"):
                    file_index[f"{coll_name}/{cam_num}/{img.name}"] = img
    print(f"  {len(file_index)} image files indexed")

    if not dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped_empty_collection = 0
    skipped_missing = 0
    already_exists = 0
    per_quoll: dict[str, int] = defaultdict(int)
    missing_examples: list[str] = []

    for _, row in df.iterrows():
        individual_id = str(row["individual_id"]).strip()
        filename = str(row["filename"]).strip()
        collection_id = str(row.get("collection_id", "")).strip()
        camera_id_raw = str(row.get("camera_id", "")).strip()

        if not individual_id or not filename:
            continue

        if not collection_id or collection_id == "nan":
            skipped_empty_collection += 1
            continue

        try:
            camera_id = int(camera_id_raw)
        except (ValueError, TypeError):
            skipped_missing += 1
            continue

        src = resolve_source_path(filename, camera_id, collection_id, cam_lookup, file_index)
        if src is None:
            skipped_missing += 1
            if len(missing_examples) < 5:
                missing_examples.append(
                    f"  {filename} (cam={camera_id}, coll={collection_id})"
                )
            continue

        # Extract collection number for the prefix
        coll_match = re.search(r"Collection-(\d+)", collection_id)
        coll_num = coll_match.group(1) if coll_match else "X"
        dest_name = f"C{coll_num}_CAM{camera_id}_{filename}"

        quoll_dir = OUTPUT_DIR / individual_id
        dest_path = quoll_dir / dest_name

        if dest_path.exists():
            already_exists += 1
            per_quoll[individual_id] += 1
            continue

        if not dry_run:
            quoll_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_path)

        copied += 1
        per_quoll[individual_id] += 1

    print()
    print("=" * 60)
    tag = "[DRY RUN] " if dry_run else ""
    print(f"{tag}Results:")
    print(f"  Images {'to copy' if dry_run else 'copied'}: {copied}")
    print(f"  Already existed (skipped): {already_exists}")
    print(f"  Skipped (empty collection): {skipped_empty_collection}")
    print(f"  Skipped (source not found): {skipped_missing}")
    print()
    print("Per-quoll breakdown:")
    for qid in sorted(per_quoll.keys()):
        print(f"  {qid}: {per_quoll[qid]} images")
    print(f"  Total quoll folders: {len(per_quoll)}")

    if missing_examples:
        print()
        print("Sample missing files:")
        for ex in missing_examples:
            print(ex)

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Organize IDed quoll images by individual")
    parser.add_argument("--dry-run", action="store_true", help="Report stats without copying")
    args = parser.parse_args()
    organize_images(dry_run=args.dry_run)
