"""Pydantic schemas for API request/response models."""
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


# --- Camera ---
class CameraBase(BaseModel):
    name: str
    camera_number: Optional[int] = None
    side: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    elevation: Optional[float] = None


class CameraOut(CameraBase):
    id: int
    model_config = {"from_attributes": True}


# --- Collection ---
class CollectionBase(BaseModel):
    name: str
    collection_number: Optional[int] = None
    date_collected: Optional[datetime] = None


class CollectionOut(CollectionBase):
    id: int
    model_config = {"from_attributes": True}


# --- Image ---
class ImageBase(BaseModel):
    filename: str
    file_path: str
    camera_id: Optional[int] = None
    collection_id: Optional[int] = None
    captured_at: Optional[datetime] = None


class ImageOut(ImageBase):
    id: int
    width: Optional[int] = None
    height: Optional[int] = None
    processed: bool = False
    has_animal: Optional[bool] = None
    thumbnail_path: Optional[str] = None
    model_config = {"from_attributes": True}


class ImageDetail(ImageOut):
    camera: Optional[CameraOut] = None
    collection: Optional[CollectionOut] = None
    detections: list["DetectionOut"] = []


# --- Detection ---
class DetectionBase(BaseModel):
    image_id: int
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    detection_confidence: float
    category: Optional[str] = None
    species: Optional[str] = None
    classification_confidence: Optional[float] = None


class DetectionOut(DetectionBase):
    id: int
    model_version: Optional[str] = None
    crop_path: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# --- Individual ---
class IndividualBase(BaseModel):
    individual_id: str
    species: str = "Spotted-tailed Quoll"
    name: Optional[str] = None


class IndividualOut(IndividualBase):
    id: int
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    total_sightings: int = 0
    model_config = {"from_attributes": True}


# --- Stats ---
class DashboardStats(BaseModel):
    total_images: int = 0
    processed_images: int = 0
    unprocessed_images: int = 0
    total_detections: int = 0
    total_animals: int = 0
    quoll_detections: int = 0
    total_individuals: int = 0
    total_cameras: int = 0
    total_collections: int = 0
    processing_percent: float = 0.0


# --- Import ---
class ImportResult(BaseModel):
    cameras_created: int = 0
    collections_created: int = 0
    images_registered: int = 0
    csv_sightings_loaded: int = 0
    individuals_created: int = 0
    errors: list[str] = []


# --- Pagination ---
class PaginatedResponse(BaseModel):
    items: list = []
    total: int = 0
    page: int = 1
    per_page: int = 50
    pages: int = 0
