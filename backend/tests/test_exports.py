"""Tests for researcher metadata exports."""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.annotation import Annotation, merge_annotation_review_fields
from backend.app.models.individual import Individual
from backend.tests.conftest import auth_header


def test_merge_annotation_review_fields_combines_split_rows():
    """Auto re-ID and a later human correction must both survive the merge."""
    auto = Annotation(
        id=1,
        detection_id=1,
        annotator="megadescriptor_reid",
        individual_id="02Q2",
        is_correct=None,
        created_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
    )
    human = Annotation(
        id=2,
        detection_id=1,
        annotator="reviewer@example.com",
        is_correct=False,
        corrected_species="Felis catus | Domestic Cat",
        notes="not a quoll",
        flag_for_retraining=True,
        created_at=datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
    )

    merged = merge_annotation_review_fields([auto, human])
    assert merged["individual_id"] == "02Q2"
    assert merged["is_correct"] is False
    assert merged["corrected_species"] == "Felis catus | Domestic Cat"
    assert merged["notes"] == "not a quoll"
    assert merged["flag_for_retraining"] is True


def test_merge_annotation_review_fields_later_assignment_wins():
    verify = Annotation(
        id=1,
        detection_id=1,
        is_correct=True,
        created_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
    )
    assign = Annotation(
        id=2,
        detection_id=1,
        is_correct=True,
        individual_id="07Q2",
        created_at=datetime(2026, 5, 1, 10, 5, tzinfo=timezone.utc),
    )
    merged = merge_annotation_review_fields([assign, verify])
    assert merged["is_correct"] is True
    assert merged["individual_id"] == "07Q2"


def test_merge_annotation_review_fields_empty():
    merged = merge_annotation_review_fields([])
    assert merged["is_correct"] is None
    assert merged["individual_id"] is None
    assert merged["flag_for_retraining"] is None


@pytest.mark.asyncio
async def test_metadata_export_requires_auth(client: AsyncClient):
    resp = await client.get("/api/exports/metadata", params={"format": "json"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_metadata_export_merges_auto_reid_and_human_review(
    client: AsyncClient,
    test_user,
    sample_data,
    db: AsyncSession,
):
    """Admin metadata CSV/JSON must not drop a later human correction.

    Trigger: MegaDescriptor auto-assign writes an individual_id-only row, then
    a reviewer marks the crop incorrect with a corrected species. Exporting
    ``annotations[0]`` (insertion order) would keep only the auto-ID.
    """
    det = sample_data["detections"][0]
    db.add(Individual(individual_id="02Q2", species="Dasyurus sp | Quoll sp"))
    t0 = datetime.now(timezone.utc)
    db.add(
        Annotation(
            detection_id=det.id,
            annotator="megadescriptor_reid",
            individual_id="02Q2",
            notes="auto re-ID sim=0.900 gap=0.100",
            created_at=t0,
        )
    )
    db.add(
        Annotation(
            detection_id=det.id,
            annotator=test_user.email,
            is_correct=False,
            corrected_species="Felis catus | Domestic Cat",
            notes="not a quoll",
            flag_for_retraining=True,
            created_at=t0 + timedelta(minutes=5),
        )
    )
    await db.commit()

    resp = await client.get(
        "/api/exports/metadata",
        params={"format": "json"},
        headers=auth_header(test_user),
    )
    assert resp.status_code == 200
    rows = resp.json()
    row = next(r for r in rows if r["detection_id"] == det.id)
    assert row["annotation_individual"] == "02Q2"
    assert row["annotation_correct"] is False
    assert row["annotation_species"] == "Felis catus | Domestic Cat"
    assert row["annotation_notes"] == "not a quoll"
    assert row["flagged_retraining"] is True
