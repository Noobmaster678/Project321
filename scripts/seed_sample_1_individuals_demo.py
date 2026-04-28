"""
Seed the Individuals UI from dataset/sample_1 (subfolder name = quoll individual ID).

Copies images into storage (uploads + crops + thumbnails) and inserts Image, Detection,
and Annotation rows so /individuals/species/.../individuals shows cards and profiles work.

Does not delete existing data; skips any file_path already in the database.

Usage (from project root):
  python scripts/seed_sample_1_individuals_demo.py
  python scripts/seed_sample_1_individuals_demo.py --max-per-id 10
  python scripts/seed_sample_1_individuals_demo.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".JPG", ".JPEG", ".PNG"}

QUOLL_SPECIES = "Dasyurus sp | Quoll sp"
DEMO_CAMERA_NAME = "Demo (sample_1)"
DEMO_COLLECTION_NAME = "Sample-1-demo"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _list_id_folders(sample_root: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    if not sample_root.is_dir():
        return out
    for child in sorted(sample_root.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            out.append((child.name, child))
    return out


def _iter_images(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix in IMAGE_EXTS)


def _make_thumb(src: Path, dest: Path, size: tuple[int, int], quality: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image as PILImage

    with PILImage.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail(size, PILImage.Resampling.LANCZOS)
        im.save(dest, "JPEG", quality=quality)


async def _main_async(args: argparse.Namespace) -> int:
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from sqlalchemy import select

    # Register all ORM relationships (Detection -> Sighting, etc.)
    from backend.app.models import (  # noqa: F401
        camera,
        collection,
        image,
        detection,
        annotation,
        individual,
        sighting,
        missed_correction,
        deployment,
        model_version,
    )
    from backend.app.models import user, job  # noqa: F401

    from backend.app.config import settings
    from backend.app.db.session import async_session_factory
    from backend.app.models.annotation import Annotation
    from backend.app.models.camera import Camera
    from backend.app.models.collection import Collection
    from backend.app.models.detection import Detection
    from backend.app.models.image import Image
    from backend.app.utils.exif import extract_image_metadata

    sample_root = Path(args.source).resolve()
    if not sample_root.is_dir():
        print(f"Source not found: {sample_root}", file=sys.stderr)
        return 1

    pairs = _list_id_folders(sample_root)
    if not pairs:
        print(f"No ID subfolders under {sample_root}", file=sys.stderr)
        return 1

    planned: list[tuple[str, Path]] = []
    for iid, folder in pairs:
        imgs = _iter_images(folder)
        if args.max_per_id > 0:
            imgs = imgs[: args.max_per_id]
        for p in imgs:
            planned.append((iid, p))

    print(f"Planned {len(planned)} images from {len(pairs)} individuals under {sample_root}")

    if args.dry_run:
        for iid, p in planned[:20]:
            print(f"  [{iid}] {p.name}")
        if len(planned) > 20:
            print(f"  ... and {len(planned) - 20} more")
        return 0

    storage = settings.STORAGE_ROOT
    tw, th = settings.THUMBNAIL_SIZE
    tq = settings.THUMBNAIL_QUALITY

    async with async_session_factory() as db:
        cam = (
            await db.execute(select(Camera).where(Camera.name == DEMO_CAMERA_NAME))
        ).scalar_one_or_none()
        if not cam:
            cam = Camera(name=DEMO_CAMERA_NAME, camera_number=999, side="demo")
            db.add(cam)
            await db.flush()

        coll = (
            await db.execute(select(Collection).where(Collection.name == DEMO_COLLECTION_NAME))
        ).scalar_one_or_none()
        if not coll:
            coll = Collection(name=DEMO_COLLECTION_NAME, collection_number=999)
            db.add(coll)
            await db.flush()

        inserted = 0
        skipped = 0

        for individual_id, src in planned:
            safe_name = src.name
            rel_upload = f"uploads/demo_sample1/{individual_id}/{safe_name}".replace("\\", "/")
            rel_crop = f"crops/demo_sample1/{individual_id}/{safe_name}".replace("\\", "/")
            stem = Path(safe_name).stem
            rel_thumb = f"thumbnails/demo_sample1/{individual_id}_{stem}.jpg".replace("\\", "/")

            exists = (
                await db.execute(select(Image.id).where(Image.file_path == rel_upload).limit(1))
            ).scalar_one_or_none()
            if exists is not None:
                skipped += 1
                continue

            up_abs = storage / rel_upload
            crop_abs = storage / rel_crop
            thumb_abs = storage / rel_thumb
            up_abs.parent.mkdir(parents=True, exist_ok=True)
            crop_abs.parent.mkdir(parents=True, exist_ok=True)

            import shutil

            shutil.copy2(src, up_abs)
            shutil.copy2(src, crop_abs)
            try:
                _make_thumb(src, thumb_abs, (tw, th), tq)
            except Exception:
                rel_thumb = ""

            meta = extract_image_metadata(src)
            cap = meta.get("captured_at")
            if cap is not None and cap.tzinfo is None:
                cap = cap.replace(tzinfo=timezone.utc)

            img = Image(
                filename=safe_name,
                file_path=rel_upload,
                camera_id=cam.id,
                collection_id=coll.id,
                captured_at=cap or datetime.now(timezone.utc),
                width=meta.get("width"),
                height=meta.get("height"),
                processed=True,
                has_animal=True,
                thumbnail_path=rel_thumb or None,
                temperature_c=meta.get("temperature_c"),
                trigger_mode=meta.get("trigger_mode"),
            )
            db.add(img)
            await db.flush()

            det = Detection(
                image_id=img.id,
                bbox_x=0.08,
                bbox_y=0.08,
                bbox_w=0.84,
                bbox_h=0.84,
                detection_confidence=0.95,
                category="animal",
                species=QUOLL_SPECIES,
                classification_confidence=0.9,
                model_version="demo_seed_sample_1",
                crop_path=rel_crop,
            )
            db.add(det)
            await db.flush()

            ann = Annotation(
                detection_id=det.id,
                annotator="demo_seed",
                individual_id=individual_id,
                is_correct=True,
                notes="Seeded from dataset/sample_1 for UI demo",
            )
            db.add(ann)
            inserted += 1

        await db.commit()

    print(f"Done. Inserted {inserted} images/detections/annotations. Skipped (already in DB): {skipped}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=_project_root() / "dataset" / "sample_1",
        help="Root folder containing per-ID subfolders (default: dataset/sample_1)",
    )
    parser.add_argument(
        "--max-per-id",
        type=int,
        default=0,
        help="Max images per individual (0 = all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List planned files only")
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
