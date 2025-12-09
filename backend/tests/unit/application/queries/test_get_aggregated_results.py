"""Unit tests for GetAggregatedResultsHandler."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import pytest

from backend.application.queries.get_aggregated_results import (
    GetAggregatedResultsHandler,
    GetAggregatedResultsQuery,
)
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.value_objects.confidence import Confidence
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.exceptions import EntityNotFoundError


class StubJobRepository(JobRepository):
    def __init__(self, jobs: List[Job]):
        self._jobs = {job.job_id: job for job in jobs}

    def save(self, job: Job) -> None:  # pragma: no cover - not required
        raise NotImplementedError

    def find_by_id(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def find_all(self, limit: Optional[int] = None, offset: int = 0, sort_desc: bool = True) -> List[Job]:  # pragma: no cover
        return list(self._jobs.values())

    def find_by_status(self, status: str, limit: Optional[int] = None, offset: int = 0, sort_desc: bool = True) -> List[Job]:  # pragma: no cover
        raise NotImplementedError

    def delete(self, job_id: str) -> bool:  # pragma: no cover
        raise NotImplementedError

    def exists(self, job_id: str) -> bool:  # pragma: no cover
        return job_id in self._jobs

    def count(self, status: Optional[str] = None) -> int:  # pragma: no cover
        return len(self._jobs)


def make_field(name: str, value: str, confidence: float, page: int) -> FieldExtraction:
    return FieldExtraction(
        field_name=name,
        value=value,
        confidence=Confidence(confidence),
        page_number=page,
    )


def make_job(job_id: str) -> Job:
    status = JobStatus.completed()
    now = datetime.now(timezone.utc)
    page1 = PageExtraction.create(page_number=1, fields=[make_field("Total", "100", 0.9, 1)])
    page2 = PageExtraction.create(page_number=2, fields=[make_field("Total", "110", 0.7, 2), make_field("Invoice", "INV-001", 0.8, 2)])
    return Job(
        job_id=job_id,
        filename="sample.pdf",
        status=status,
        total_pages=2,
        pages=[page1, page2],
        created_at=now,
        updated_at=now,
        source_path=None,
    )


def test_returns_aggregated_results():
    job = make_job("job-1")
    handler = GetAggregatedResultsHandler(StubJobRepository([job]))

    dto = handler.handle(GetAggregatedResultsQuery(job_id="job-1"))

    assert dto.job_id == "job-1"
    assert len(dto.fields) == 2
    total_field = next(field for field in dto.fields if field.canonical_name == "Total")
    assert total_field.best_value == "100"
    assert total_field.confidence_stats["max"] == 0.9


def test_raises_for_missing_job():
    handler = GetAggregatedResultsHandler(StubJobRepository([]))
    with pytest.raises(EntityNotFoundError):
        handler.handle(GetAggregatedResultsQuery(job_id="missing"))
