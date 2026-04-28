"""FastAPI application entrypoint."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.db.session import engine
from backend.app.db.base import Base

# Import all models so they register with Base.metadata
from backend.app.models import (  # noqa: F401
    camera, collection, image, detection, annotation, individual, sighting,
    missed_correction, deployment, model_version,
)
from backend.app.models import user, job  # noqa: F401

# Import routers
from backend.app.api import images, detections, stats, auth, annotations, admin, reports, exports, reid, individuals


async def _sqlite_ensure_columns(conn) -> None:
    """
    Lightweight SQLite schema patching (no Alembic).

    Ensures new nullable columns exist on existing DBs created before model changes.
    """
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return
    try:
        rows = (await conn.exec_driver_sql("PRAGMA table_info(individuals)")).all()
        existing = {r[1] for r in rows}  # name column
        if "ref_left_detection_id" not in existing:
            await conn.exec_driver_sql("ALTER TABLE individuals ADD COLUMN ref_left_detection_id INTEGER")
        if "ref_right_detection_id" not in existing:
            await conn.exec_driver_sql("ALTER TABLE individuals ADD COLUMN ref_right_detection_id INTEGER")
    except Exception:
        # If table doesn't exist yet, create_all below will handle it.
        return


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _sqlite_ensure_columns(conn)
    yield
    await engine.dispose()


app = FastAPI(
    title="Wildlife AI Platform",
    description="Camera trap image processing for Spotted-tailed Quoll identification",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists(settings.STORAGE_ROOT):
    app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_ROOT)), name="storage")

app.include_router(auth.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(detections.router, prefix="/api")
app.include_router(annotations.router, prefix="/api")
app.include_router(individuals.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(reid.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/")
async def root():
    return {"name": "Wildlife AI Platform", "version": "1.0.0", "docs": "/docs", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
