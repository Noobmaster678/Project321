"""Regression: multi-chunk batch jobs must not complete before all images are counted."""
from backend.worker.tasks import resolve_batch_job_completion


def test_first_chunk_does_not_complete_when_total_still_higher():
    """Frontend uploads in 200-file chunks; first Celery task must stay open."""
    is_terminal, status, error = resolve_batch_job_completion(
        total_images=400,
        processed_images=200,
        failed_images=0,
    )
    assert is_terminal is False
    assert status is None
    assert error is None


def test_final_chunk_completes_when_counters_cover_total():
    is_terminal, status, error = resolve_batch_job_completion(
        total_images=400,
        processed_images=400,
        failed_images=0,
    )
    assert is_terminal is True
    assert status == "completed"
    assert error is None


def test_completion_with_failures_requires_full_coverage():
    is_terminal, status, error = resolve_batch_job_completion(
        total_images=10,
        processed_images=7,
        failed_images=2,
        chunk_failed_ids=[99],
    )
    assert is_terminal is False

    is_terminal, status, error = resolve_batch_job_completion(
        total_images=10,
        processed_images=8,
        failed_images=2,
        chunk_failed_ids=[99],
    )
    assert is_terminal is True
    assert status == "completed_with_errors"
    assert "99" in (error or "")
