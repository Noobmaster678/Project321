"""
Inference for a 5-quoll MegaDescriptor checkpoint.

Given a query image, it embeds it and compares to a gallery built from the
TRAIN images for each identity (subfolder). It outputs:
- top-1 predicted quoll ID
- cosine scores for each class (best match within that class)
- score gap (top1 - top2)

Example:
  python -m scripts.test_megadescriptor_5quolls_inference ^
    --query "I:/.../5 quolls/02Q3/some_crop.jpg" ^
    --root-dir "I:/AA-Study/Project321/dataset/IDed images/crops/5 quolls" ^
    --model "storage/models/megadescriptor_5quolls.pt"
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torchvision import models, transforms


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".JPG", ".JPEG", ".PNG"}


class MegaDescriptor(nn.Module):
    def __init__(self, embedding_dim: int, num_classes: int):
        super().__init__()
        backbone = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        feat_dim = backbone.fc.in_features
        backbone.fc = nn.Identity()
        self.backbone = backbone
        self.proj = nn.Sequential(
            nn.Linear(feat_dim, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(512, embedding_dim),
        )
        self.classifier = nn.Linear(embedding_dim, num_classes)

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        z = self.proj(self.backbone(x))
        return F.normalize(z, p=2, dim=1)


def list_images(folder: Path) -> list[Path]:
    return sorted([p for p in folder.rglob("*") if p.is_file() and p.suffix in IMAGE_EXTS])


def build_transform(image_size: int = 224):
    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )


def embed_one(model: MegaDescriptor, path: Path, tf, device: str) -> torch.Tensor:
    with Image.open(path) as img:
        img = img.convert("RGB")
        x = tf(img).unsqueeze(0).to(device)
    with torch.no_grad():
        z = model.embed(x).cpu().squeeze(0)
    return z


def main() -> None:
    parser = argparse.ArgumentParser(description="Inference on 5-quoll MegaDescriptor model")
    parser.add_argument("--query", type=Path, required=True)
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("storage/models/megadescriptor_5quolls.pt"),
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path(r"I:/AA-Study/Project321/dataset/IDed images/crops/5 quolls"),
        help="Folder with 5 ID subfolders used as gallery",
    )
    parser.add_argument(
        "--true-id",
        type=str,
        default=None,
        help="Optional ground-truth ID for correctness check (e.g., 02Q2)",
    )
    parser.add_argument("--max-per-id", type=int, default=200, help="Cap gallery images per ID")
    parser.add_argument("--seed", type=int, default=123, help="Sampling seed for gallery cap")
    args = parser.parse_args()

    if not args.query.exists():
        raise FileNotFoundError(f"Query not found: {args.query}")
    if not args.model.exists():
        raise FileNotFoundError(f"Model not found: {args.model}")
    if not args.root_dir.exists():
        raise FileNotFoundError(f"Root dir not found: {args.root_dir}")

    ckpt = torch.load(args.model, map_location="cpu")
    embedding_dim = int(ckpt["embedding_dim"])
    class_names = list(ckpt.get("class_names") or [])

    # If checkpoint lacks class_names, infer from root dir
    if not class_names:
        class_names = sorted([p.name for p in args.root_dir.iterdir() if p.is_dir()])

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = MegaDescriptor(embedding_dim=embedding_dim, num_classes=len(class_names)).to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    tf = build_transform(224)
    q = embed_one(model, args.query, tf, device)

    rng = random.Random(args.seed)
    per_class_best: dict[str, float] = {}

    for name in class_names:
        folder = args.root_dir / name
        paths = list_images(folder)
        if not paths:
            continue
        if args.max_per_id and len(paths) > args.max_per_id:
            paths = paths[:]
            rng.shuffle(paths)
            paths = paths[: args.max_per_id]

        best = -1.0
        for p in paths:
            if p.resolve() == args.query.resolve():
                continue
            z = embed_one(model, p, tf, device)
            s = float((z * q).sum().item())
            if s > best:
                best = s
        per_class_best[name] = best

    ranked = sorted(per_class_best.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        raise ValueError("No gallery images found.")

    top1, s1 = ranked[0]
    top2, s2 = ranked[1] if len(ranked) > 1 else ("<none>", -1.0)

    inferred_true = None
    try:
        rel = args.query.resolve().relative_to(args.root_dir.resolve())
        inferred_true = rel.parts[0] if len(rel.parts) > 1 else None
    except Exception:
        inferred_true = None
    true_id = args.true_id or inferred_true

    print("=" * 60)
    print("MegaDescriptor 5-quoll inference")
    print("=" * 60)
    print(f"Query:  {args.query}")
    print(f"Model:  {args.model}")
    print(f"Device: {device}")
    print("-" * 60)
    print(f"Top-1: {top1}  score={s1:.4f}")
    print(f"Top-2: {top2}  score={s2:.4f}")
    print(f"Gap:   {(s1 - s2):.4f}")
    if true_id:
        outcome = "CORRECT" if top1 == true_id else "INCORRECT"
        print(f"Truth: {true_id} -> {outcome}")
    print("-" * 60)
    for name, s in ranked:
        print(f"{name:>8}: {s:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()

