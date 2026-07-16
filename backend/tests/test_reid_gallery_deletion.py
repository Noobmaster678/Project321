"""Regression tests for removing deleted identities from the re-ID gallery."""
import torch

from backend.worker.pipelines import megadescriptor_reid


def test_remove_individual_from_gallery(tmp_path):
    gallery = tmp_path / "gallery.pt"
    torch.save(
        {
            "prototypes": torch.tensor(
                [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ]
            ),
            "class_names": ["01Q1", "02Q2", "03Q3"],
            "prototype_counts": [2, 4, 6],
            "gallery_version": 7,
            "model_name": "test-model",
        },
        gallery,
    )
    megadescriptor_reid._state = {"path": str(gallery.resolve())}

    assert megadescriptor_reid.remove_individual_from_gallery(gallery, "02Q2") is True

    updated = torch.load(gallery, map_location="cpu", weights_only=False)
    assert updated["class_names"] == ["01Q1", "03Q3"]
    assert updated["prototype_counts"] == [2, 6]
    assert torch.equal(
        updated["prototypes"],
        torch.tensor([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]),
    )
    assert updated["gallery_version"] == 8
    assert updated["model_name"] == "test-model"
    assert megadescriptor_reid._state is None
