"""Regression tests for CSV ground-truth import image matching."""
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.camera import Camera
from backend.app.models.collection import Collection
from backend.app.models.image import Image
from backend.app.models.individual import Individual
from backend.app.models.sighting import Sighting
from scripts.bulk_import import find_image_for_csv_row, load_csv_ground_truth


async def _seed_reconyx_collision(db: AsyncSession) -> dict:
    """Two cameras in one collection both have RCNX0001.JPG (normal Reconyx naming)."""
    coll = Collection(name="Collection-1_11-10-2023", collection_number=1)
    cam_1a = Camera(name="1A", camera_number=1, side="A")
    cam_2a = Camera(name="2A", camera_number=2, side="A")
    db.add_all([coll, cam_1a, cam_2a])
    await db.flush()

    img_1a = Image(
        filename="RCNX0001.JPG",
        file_path="MORTON NP PHOTOS/Collection-1_11-10-2023/1A_11-10-23/RCNX0001.JPG",
        camera_id=cam_1a.id,
        collection_id=coll.id,
    )
    img_2a = Image(
        filename="RCNX0001.JPG",
        file_path="MORTON NP PHOTOS/Collection-1_11-10-2023/2A_11-10-23/RCNX0001.JPG",
        camera_id=cam_2a.id,
        collection_id=coll.id,
    )
    db.add_all([img_1a, img_2a])
    await db.commit()
    await db.refresh(img_1a)
    await db.refresh(img_2a)
    return {"collection": coll, "cam_1a": cam_1a, "cam_2a": cam_2a, "img_1a": img_1a, "img_2a": img_2a}


@pytest.mark.asyncio
async def test_find_image_filename_only_is_ambiguous(db: AsyncSession):
    seeded = await _seed_reconyx_collision(db)
    img, err = await find_image_for_csv_row(
        db,
        filename="RCNX0001.JPG",
        collection_name="Collection-1_11-10-2023",
        camera_number=None,
    )
    assert img is None
    assert err is not None
    assert "Ambiguous" in err
    assert seeded["img_1a"].id != seeded["img_2a"].id


@pytest.mark.asyncio
async def test_find_image_uses_camera_number_to_disambiguate(db: AsyncSession):
    seeded = await _seed_reconyx_collision(db)
    img, err = await find_image_for_csv_row(
        db,
        filename="RCNX0001.JPG",
        collection_name="Collection-1_11-10-2023",
        camera_number=2,
    )
    assert err is None
    assert img is not None
    assert img.id == seeded["img_2a"].id


@pytest.mark.asyncio
async def test_csv_import_attaches_sighting_to_matching_camera(db: AsyncSession, tmp_path: Path):
    seeded = await _seed_reconyx_collision(db)
    csv_path = tmp_path / "stq.csv"
    csv_path.write_text(
        "individual_id,filename,identified_by,camera_id,collection_id,timestamp,common_name\n"
        "02Q1,RCNX0001.JPG,Jordyn,2,Collection-1_11-10-2023,11-10-2023 08:15,Spotted-tailed Quoll\n",
        encoding="utf-8",
    )

    stats = await load_csv_ground_truth(db, csv_path)
    assert stats["csv_sightings_loaded"] == 1
    assert stats["errors"] == []

    sight = (await db.execute(select(Sighting))).scalar_one()
    assert sight.image_id == seeded["img_2a"].id
    assert sight.image_id != seeded["img_1a"].id

    ind = (await db.execute(select(Individual).where(Individual.individual_id == "02Q1"))).scalar_one()
    assert ind.total_sightings == 1


@pytest.mark.asyncio
async def test_csv_import_pandas_float_camera_id(db: AsyncSession, tmp_path: Path):
    """pandas often reads camera_id as 1.0; matching must still succeed."""
    seeded = await _seed_reconyx_collision(db)
    csv_path = tmp_path / "stq.csv"
    csv_path.write_text(
        "individual_id,filename,camera_id,collection_id\n"
        "07Q2,RCNX0001.JPG,1.0,Collection-1_11-10-2023\n",
        encoding="utf-8",
    )

    stats = await load_csv_ground_truth(db, csv_path)
    assert stats["csv_sightings_loaded"] == 1
    assert stats["errors"] == []
    sight = (await db.execute(select(Sighting))).scalar_one()
    assert sight.image_id == seeded["img_1a"].id
