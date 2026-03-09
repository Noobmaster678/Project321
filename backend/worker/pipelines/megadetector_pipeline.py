"""
MegaDetector Pipeline
=====================
Loads MegaDetector v5a and runs batch inference on images.
Returns bounding boxes for detected animals.
"""
import torch
import numpy as np
from pathlib import Path
from PIL import Image
from typing import Optional

from backend.app.config import settings


class MegaDetectorPipeline:
    """MegaDetector v5a wrapper for animal detection."""

    # MegaDetector categories
    CATEGORIES = {1: "animal", 2: "person", 3: "vehicle"}

    def __init__(self, model_path: Optional[Path] = None, device: Optional[str] = None):
        self.model_path = model_path or settings.MEGADETECTOR_MODEL_PATH
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.confidence_threshold = settings.DETECTION_CONFIDENCE_THRESHOLD

    def load_model(self):
        """Load the MegaDetector YOLOv5 model."""
        if self.model is not None:
            return

        print(f"Loading MegaDetector from {self.model_path}...")
        print(f"Device: {self.device}")

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"MegaDetector weights not found at {self.model_path}. "
                f"Download from: https://github.com/agentmorris/MegaDetector/releases/download/v5.0/md_v5a.0.0.pt"
            )

        # Load YOLOv5 model via torch.hub or megadetector package
        try:
            from megadetector.detection.run_detector import load_detector
            self.model = load_detector(str(self.model_path))
            print("✅ MegaDetector loaded via megadetector package")
        except ImportError:
            # Fallback: load via torch hub
            self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=str(self.model_path))
            self.model.to(self.device)
            self.model.conf = self.confidence_threshold
            print("✅ MegaDetector loaded via torch.hub")

    def detect_single(self, image_path: str | Path) -> list[dict]:
        """
        Run MegaDetector on a single image.

        Returns list of detections:
        [
            {
                "bbox": [x, y, w, h],  # normalized 0-1
                "confidence": 0.95,
                "category": "animal"
            }
        ]
        """
        self.load_model()

        try:
            from megadetector.detection.run_detector import run_detector_on_image
            result = run_detector_on_image(self.model, str(image_path))

            detections = []
            if "detections" in result:
                for det in result["detections"]:
                    conf = det.get("conf", 0.0)
                    if conf < self.confidence_threshold:
                        continue

                    category_id = det.get("category", "1")
                    category = self.CATEGORIES.get(int(category_id), "unknown")

                    bbox = det.get("bbox", [0, 0, 0, 0])  # [x, y, w, h] normalized
                    detections.append({
                        "bbox": bbox,
                        "confidence": conf,
                        "category": category,
                    })

            return detections

        except ImportError:
            # Fallback: use YOLOv5 directly
            img = Image.open(image_path)
            results = self.model(img)

            detections = []
            for *xyxy, conf, cls in results.xyxy[0].cpu().numpy():
                if conf < self.confidence_threshold:
                    continue

                # Convert from xyxy to normalized xywh
                w_img, h_img = img.size
                x1, y1, x2, y2 = xyxy
                bbox = [
                    x1 / w_img,
                    y1 / h_img,
                    (x2 - x1) / w_img,
                    (y2 - y1) / h_img,
                ]

                category = self.CATEGORIES.get(int(cls) + 1, "unknown")
                detections.append({
                    "bbox": bbox,
                    "confidence": float(conf),
                    "category": category,
                })

            return detections

    def detect_batch(self, image_paths: list[str | Path]) -> list[list[dict]]:
        """Run MegaDetector on a batch of images."""
        self.load_model()
        results = []
        for path in image_paths:
            try:
                dets = self.detect_single(path)
                results.append(dets)
            except Exception as e:
                print(f"  ⚠️ Error processing {path}: {e}")
                results.append([])
        return results

    def crop_detection(
        self,
        image_path: str | Path,
        bbox: list[float],
        output_path: str | Path,
        padding: float = 0.1,
    ) -> Path:
        """
        Crop a detection from an image and save it.

        Args:
            image_path: Path to source image
            bbox: [x, y, w, h] normalized 0-1
            output_path: Where to save the crop
            padding: Extra padding around bbox (fraction of bbox size)

        Returns:
            Path to saved crop
        """
        img = Image.open(image_path)
        w_img, h_img = img.size

        x, y, w, h = bbox
        # Add padding
        pad_x = w * padding
        pad_y = h * padding

        x1 = max(0, int((x - pad_x) * w_img))
        y1 = max(0, int((y - pad_y) * h_img))
        x2 = min(w_img, int((x + w + pad_x) * w_img))
        y2 = min(h_img, int((y + h + pad_y) * h_img))

        crop = img.crop((x1, y1, x2, y2))

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(str(output_path), quality=95)

        return output_path
