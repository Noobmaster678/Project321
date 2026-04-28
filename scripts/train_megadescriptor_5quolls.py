"""
Train MegaDescriptor on 5 labeled quoll folders and evaluate re-ID.

Dataset expected:
    I:/AA-Study/Project321/dataset/IDed images/crops/5 quolls/
        02Q2/ *.jpg
        02Q3/ *.jpg
        ... (5 folders total)

This script trains a backbone+embedding with a classification head (5-way),
then evaluates retrieval-style performance using a gallery built from TRAIN
embeddings and queries from TEST embeddings.
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".JPG", ".JPEG", ".PNG"}


def list_images(folder: Path) -> list[Path]:
    return sorted([p for p in folder.rglob("*") if p.is_file() and p.suffix in IMAGE_EXTS])


def list_id_folders(root: Path) -> list[Path]:
    return sorted([p for p in root.iterdir() if p.is_dir()])


def stable_shuffle(items: list, seed: int) -> list:
    rng = random.Random(seed)
    out = items[:]
    rng.shuffle(out)
    return out


def split_per_id(
    id_to_paths: dict[str, list[Path]],
    test_ratio: float,
    seed: int,
) -> tuple[list[tuple[Path, int]], list[tuple[Path, int]], list[str]]:
    """Returns (train_items, test_items, id_names) where items are (path, class_idx)."""
    id_names = sorted(id_to_paths.keys())
    train: list[tuple[Path, int]] = []
    test: list[tuple[Path, int]] = []
    for cls_idx, qid in enumerate(id_names):
        paths = stable_shuffle(id_to_paths[qid], seed=seed + cls_idx * 997)
        if len(paths) < 4:
            raise ValueError(f"Need >=4 images for {qid}, found {len(paths)}")
        n_test = max(1, int(len(paths) * test_ratio))
        n_test = min(n_test, len(paths) - 2)  # keep at least 2 train
        test_paths = paths[:n_test]
        train_paths = paths[n_test:]
        train.extend([(p, cls_idx) for p in train_paths])
        test.extend([(p, cls_idx) for p in test_paths])
    return train, test, id_names


class LabeledImageDataset(Dataset):
    def __init__(self, items: list[tuple[Path, int]], image_size: int = 224, train: bool = False):
        self.items = items
        if train:
            self.tf = transforms.Compose(
                [
                    transforms.Resize((image_size, image_size)),
                    transforms.RandomHorizontalFlip(p=0.5),
                    transforms.RandomRotation(12),
                    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.15, hue=0.03),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ]
            )
        else:
            self.tf = transforms.Compose(
                [
                    transforms.Resize((image_size, image_size)),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
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

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        emb = self.embed(x)
        logits = self.classifier(emb)
        return emb, logits


@dataclass
class RunConfig:
    root_dir: Path
    epochs: int
    batch_size: int
    lr: float
    test_ratio: float
    seed: int
    embedding_dim: int
    output: Path


def batched(iterable: Iterable, n: int):
    batch = []
    for x in iterable:
        batch.append(x)
        if len(batch) == n:
            yield batch
            batch = []
    if batch:
        yield batch


def compute_gallery(
    model: MegaDescriptor,
    loader: DataLoader,
    device: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Returns (gallery_embs [N,D], gallery_labels [N])."""
    model.eval()
    all_embs = []
    all_y = []
    with torch.no_grad():
        for x, y, _ in loader:
            x = x.to(device)
            emb = model.embed(x).cpu()
            all_embs.append(emb)
            all_y.append(y.cpu())
    return torch.cat(all_embs, dim=0), torch.cat(all_y, dim=0)


def eval_rank1(
    model: MegaDescriptor,
    gallery_embs: torch.Tensor,
    gallery_y: torch.Tensor,
    query_loader: DataLoader,
    device: str,
    num_classes: int,
) -> None:
    model.eval()
    correct = 0
    total = 0
    confusion = torch.zeros((num_classes, num_classes), dtype=torch.int64)

    with torch.no_grad():
        for x, y, _ in query_loader:
            x = x.to(device)
            q = model.embed(x).cpu()  # [B,D]
            sims = q @ gallery_embs.T  # [B,N]
            nn_idx = sims.argmax(dim=1)  # [B]
            pred = gallery_y[nn_idx]  # [B]
            y_cpu = y.cpu()
            correct += int((pred == y_cpu).sum().item())
            total += int(y_cpu.numel())
            for t, p in zip(y_cpu.tolist(), pred.tolist()):
                confusion[t, p] += 1

    acc = correct / max(1, total)
    print("=" * 60)
    print("Evaluation (retrieval, Rank-1 via nearest neighbor)")
    print("=" * 60)
    print(f"Queries: {total}, Correct: {correct}, Rank-1 acc: {acc*100:.2f}%")
    print("Confusion (rows=true, cols=pred):")
    print(confusion)


def run(cfg: RunConfig) -> None:
    if not cfg.root_dir.exists():
        raise FileNotFoundError(f"Root dir not found: {cfg.root_dir}")

    id_folders = list_id_folders(cfg.root_dir)
    if len(id_folders) != 5:
        print(f"WARNING: expected 5 folders, found {len(id_folders)}")

    id_to_paths: dict[str, list[Path]] = {}
    for d in id_folders:
        paths = list_images(d)
        if not paths:
            raise ValueError(f"No images in {d}")
        id_to_paths[d.name] = paths

    train_items, test_items, id_names = split_per_id(id_to_paths, cfg.test_ratio, cfg.seed)
    num_classes = len(id_names)
    print(f"IDs ({num_classes}): {id_names}")
    print(f"Items: train={len(train_items)}, test={len(test_items)}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    model = MegaDescriptor(embedding_dim=cfg.embedding_dim, num_classes=num_classes).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=1e-4)
    ce = nn.CrossEntropyLoss()

    train_loader = DataLoader(
        LabeledImageDataset(train_items, train=True),
        batch_size=min(cfg.batch_size, len(train_items)),
        shuffle=True,
        num_workers=0,
    )
    test_loader = DataLoader(
        LabeledImageDataset(test_items, train=False),
        batch_size=cfg.batch_size,
        shuffle=False,
        num_workers=0,
    )
    gallery_loader = DataLoader(
        LabeledImageDataset(train_items, train=False),
        batch_size=cfg.batch_size,
        shuffle=False,
        num_workers=0,
    )

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        losses: list[float] = []
        accs: list[float] = []
        for x, y, _ in train_loader:
            x = x.to(device)
            y = y.to(device)
            _, logits = model(x)
            loss = ce(logits, y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.item()))
            accs.append(float((logits.argmax(dim=1) == y).float().mean().item()))
        print(
            f"epoch {epoch:02d}/{cfg.epochs} - "
            f"loss={sum(losses)/max(1,len(losses)):.4f} "
            f"train_acc={sum(accs)/max(1,len(accs))*100:.1f}%"
        )

    gallery_embs, gallery_y = compute_gallery(model, gallery_loader, device)
    eval_rank1(model, gallery_embs, gallery_y, test_loader, device, num_classes=num_classes)

    cfg.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "embedding_dim": cfg.embedding_dim,
            "class_names": id_names,
            "root_dir": str(cfg.root_dir),
            "train_count": len(train_items),
            "test_count": len(test_items),
            "mode": "five_id_supervised_ce",
        },
        cfg.output,
    )
    print(f"Saved model to: {cfg.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train MegaDescriptor on 5 quolls")
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path(r"I:/AA-Study/Project321/dataset/IDed images/crops/5 quolls"),
        help="Folder containing 5 ID subfolders",
    )
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--embedding-dim", type=int, default=256)
    parser.add_argument("--output", type=Path, default=Path("storage/models/megadescriptor_5quolls.pt"))
    args = parser.parse_args()

    cfg = RunConfig(
        root_dir=args.root_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        test_ratio=args.test_ratio,
        seed=args.seed,
        embedding_dim=args.embedding_dim,
        output=args.output,
    )
    run(cfg)


if __name__ == "__main__":
    main()

