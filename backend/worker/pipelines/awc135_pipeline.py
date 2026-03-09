"""
AWC135 Species Classification Pipeline
=======================================
Loads the AWC135 Australian Wildlife Classifier and classifies
cropped animal detections by species.
"""
import torch
import torch.nn.functional as F
from pathlib import Path
from PIL import Image
from torchvision import transforms
from typing import Optional

from backend.app.config import settings


class AWC135Pipeline:
    """AWC135 species classifier wrapper."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        labels_path: Optional[Path] = None,
        device: Optional[str] = None,
    ):
        self.model_path = model_path or settings.AWC135_MODEL_PATH
        self.labels_path = labels_path or settings.AWC135_LABELS_PATH
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.labels = None
        self.confidence_threshold = settings.CLASSIFICATION_CONFIDENCE_THRESHOLD

        # Standard ImageNet transforms for classification
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def load_model(self):
        """Load AWC135 classifier model and labels."""
        if self.model is not None:
            return

        print(f"Loading AWC135 classifier from {self.model_path}...")
        print(f"Device: {self.device}")

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"AWC135 weights not found at {self.model_path}. "
                f"Download from: https://github.com/Australian-Wildlife-Conservancy-AWC/awc-wildlife-classifier"
            )

        # Load labels
        if self.labels_path.exists():
            with open(self.labels_path, "r") as f:
                self.labels = [line.strip() for line in f.readlines()]
            print(f"  Loaded {len(self.labels)} species labels")
        else:
            print(f"  ⚠️ Labels file not found at {self.labels_path}")
            self.labels = [f"class_{i}" for i in range(135)]

        # Try loading via awc_helpers first
        try:
            from awc_helpers.classifier import load_classifier
            self.model = load_classifier(str(self.model_path))
            if hasattr(self.model, 'to'):
                self.model.to(self.device)
            if hasattr(self.model, 'eval'):
                self.model.eval()
            print("✅ AWC135 loaded via awc_helpers")
            return
        except ImportError:
            pass

        # Fallback: load as standard PyTorch model
        try:
            self.model = torch.load(str(self.model_path), map_location=self.device)
            if hasattr(self.model, 'eval'):
                self.model.eval()
            print("✅ AWC135 loaded via torch.load")
        except Exception as e:
            print(f"  ⚠️ Could not load model directly: {e}")
            # Try loading state dict with a default architecture
            checkpoint = torch.load(str(self.model_path), map_location=self.device)
            if isinstance(checkpoint, dict) and 'model' in checkpoint:
                self.model = checkpoint['model']
                if hasattr(self.model, 'eval'):
                    self.model.eval()
                print("✅ AWC135 loaded from checkpoint dict")
            else:
                raise RuntimeError(f"Could not load AWC135 model from {self.model_path}")

    def classify_single(self, image_path: str | Path) -> dict:
        """
        Classify a single cropped image.

        Returns:
            {
                "species": "Spotted-tailed Quoll",
                "confidence": 0.87,
                "top5": [("Spotted-tailed Quoll", 0.87), ("Brush-tailed Possum", 0.05), ...]
            }
        """
        self.load_model()

        try:
            img = Image.open(image_path).convert("RGB")
            tensor = self.transform(img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                output = self.model(tensor)
                probs = F.softmax(output, dim=1)[0]

            # Get top predictions
            top_k = min(5, len(probs))
            top_probs, top_indices = torch.topk(probs, top_k)

            top5 = []
            for prob, idx in zip(top_probs.cpu().numpy(), top_indices.cpu().numpy()):
                species = self.labels[idx] if idx < len(self.labels) else f"class_{idx}"
                top5.append((species, float(prob)))

            best_species, best_conf = top5[0]

            return {
                "species": best_species,
                "confidence": best_conf,
                "top5": top5,
            }
        except Exception as e:
            return {
                "species": None,
                "confidence": 0.0,
                "top5": [],
                "error": str(e),
            }

    def classify_batch(self, image_paths: list[str | Path]) -> list[dict]:
        """Classify a batch of cropped images."""
        self.load_model()
        results = []
        for path in image_paths:
            try:
                result = self.classify_single(path)
                results.append(result)
            except Exception as e:
                results.append({
                    "species": None,
                    "confidence": 0.0,
                    "top5": [],
                    "error": str(e),
                })
        return results

    def is_target_species(self, classification: dict) -> bool:
        """Check if the classification matches the target species (quoll)."""
        species = classification.get("species", "")
        confidence = classification.get("confidence", 0.0)

        if species is None:
            return False

        target = settings.TARGET_SPECIES.lower()
        return (
            target in species.lower()
            and confidence >= self.confidence_threshold
        )
