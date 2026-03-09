"""
FastAPI application entrypoint.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.db.session import engine
from backend.app.db.base import Base

# Import all models so they register with Base.metadata
from backend.app.models import camera, collection, image, detection, annotation, individual, sighting  # noqa: F401

# Import routers
from backend.app.api import images, detections, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables ready.")
    yield
    await engine.dispose()


app = FastAPI(
    title="Wildlife AI Platform",
    description="Camera trap image processing for Spotted-tailed Quoll identification",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for serving thumbnails and crops
import os
if os.path.exists(settings.STORAGE_ROOT):
    app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_ROOT)), name="storage")

# API routers
app.include_router(images.router, prefix="/api")
app.include_router(detections.router, prefix="/api")
app.include_router(stats.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "Wildlife AI Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
