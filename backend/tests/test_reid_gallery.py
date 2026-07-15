"""Concurrency tests for the persisted MegaDescriptor gallery."""

from concurrent.futures import ThreadPoolExecutor
import time

import torch

from backend.worker.pipelines import megadescriptor_reid


def _load_checkpoint(path):
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


def test_incremental_gallery_updates_are_serialized(tmp_path, monkeypatch):
    """Concurrent writers must preserve every prototype count update."""
    gallery_path = tmp_path / "gallery.pt"
    torch.save(
        {
            "prototypes": torch.tensor([[1.0, 0.0, 0.0]]),
            "class_names": ["02Q2"],
            "prototype_counts": [1],
            "gallery_version": 1,
        },
        gallery_path,
    )

    def load_state(path):
        checkpoint = _load_checkpoint(path)
        # Widen the read/modify/write race that existed before gallery locking.
        time.sleep(0.01)
        stat = path.stat()
        return {
            "path": str(path.resolve()),
            "prototypes": checkpoint["prototypes"],
            "class_names": checkpoint["class_names"],
            "prototype_counts": checkpoint["prototype_counts"],
            "gallery_version": checkpoint["gallery_version"],
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }

    monkeypatch.setattr(megadescriptor_reid, "_ensure_state", load_state)
    embedding = torch.tensor([1.0, 0.0, 0.0])

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: megadescriptor_reid.incremental_update_gallery(
                    gallery_path,
                    "02Q2",
                    embedding,
                ),
                range(16),
            )
        )

    checkpoint = _load_checkpoint(gallery_path)
    assert all(results)
    assert checkpoint["class_names"] == ["02Q2"]
    assert checkpoint["prototype_counts"] == [17]
    assert checkpoint["gallery_version"] == 17
    assert not list(tmp_path.glob(f".{gallery_path.name}.*.tmp"))
