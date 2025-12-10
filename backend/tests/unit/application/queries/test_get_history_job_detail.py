"""Unit tests for GetHistoryJobDetailHandler."""
from __future__ import annotations

import pytest

from backend.application.queries.get_history_job_detail import (
    GetHistoryJobDetailHandler,
    GetHistoryJobDetailQuery,
)
from backend.domain.exceptions import EntityNotFoundError
from pathlib import Path

from backend.models.job import ExtractionJob, JobStatus


def make_job(job_id: str) -> ExtractionJob:
    status = JobStatus(job_id=job_id, total_pages=1)
    dummy_path = Path(f"/tmp/{job_id}.pdf")
    return ExtractionJob(status=status, pdf_path=dummy_path, output_dir=dummy_path.parent, pages=[])


def test_returns_job_when_loader_succeeds():
    handler = GetHistoryJobDetailHandler(lambda job_id: make_job(job_id))
    result = handler.handle(GetHistoryJobDetailQuery(job_id="abc"))
    assert result.status.job_id == "abc"


def test_raises_when_job_missing():
    handler = GetHistoryJobDetailHandler(lambda job_id: None)
    with pytest.raises(EntityNotFoundError):
        handler.handle(GetHistoryJobDetailQuery(job_id="missing"))
