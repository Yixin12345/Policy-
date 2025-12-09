"""Unit tests for ListLowConfidenceFieldsHandler."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from backend.application.queries.list_low_confidence_fields import (
    ListLowConfidenceFieldsHandler,
    ListLowConfidenceFieldsQuery,
)
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.value_objects.job_status import JobStatus


class StubJobRepository(JobRepository):
    """In-memory repository for low-confidence field tests."""

    def __init__(self, jobs: List[Job]):
        self._jobs = jobs

    def save(self, job: Job) -> None:  # pragma: no cover - not required
        raise NotImplementedError

    def find_by_id(self, job_id: str) -> Optional[Job]:  # pragma: no cover - not required
        return next((job for job in self._jobs if job.job_id == job_id), None)

    def find_all(self, limit: Optional[int] = None, offset: int = 0, sort_desc: bool = True) -> List[Job]:
        return list(self._jobs)

    def find_by_status(
        self,
        status: str,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> List[Job]:  # pragma: no cover - not required
        raise NotImplementedError

    def delete(self, job_id: str) -> bool:  # pragma: no cover - not required
        raise NotImplementedError

    def exists(self, job_id: str) -> bool:  # pragma: no cover - not required
        return any(job.job_id == job_id for job in self._jobs)

    def count(self, status: Optional[str] = None) -> int:  # pragma: no cover - not required
        return len(self._jobs)


def make_job(job_id: str, confidences: List[float]) -> Job:
    fields = [
        FieldExtraction.create(
            field_name=f"field-{index}",
            value=f"value-{index}",
            confidence=confidence,
        )
        for index, confidence in enumerate(confidences, start=1)
    ]
    page = PageExtraction.create(page_number=1, fields=fields)
    now = datetime.now(timezone.utc)
    return Job(
        job_id=job_id,
        filename=f"{job_id}.pdf",
        status=JobStatus.completed(),
        total_pages=1,
        pages=[page],
        created_at=now,
        updated_at=now,
        source_path=None,
    )


def test_returns_low_confidence_fields_sorted():
    job = make_job("job-a", [0.35, 0.55, 0.2])
    handler = ListLowConfidenceFieldsHandler(StubJobRepository([job]))

    results = handler.handle(ListLowConfidenceFieldsQuery())

    assert [item.name for item in results] == ["field-3", "field-1"]
    assert results[0].confidence <= results[1].confidence


def test_applies_limit_and_job_filter():
    job_a = make_job("job-a", [0.3, 0.8])
    job_b = make_job("job-b", [0.25])
    handler = ListLowConfidenceFieldsHandler(StubJobRepository([job_a, job_b]))

    limited = handler.handle(ListLowConfidenceFieldsQuery(limit=1))
    assert len(limited) == 1

    filtered = handler.handle(ListLowConfidenceFieldsQuery(job_id="job-b"))
    assert len(filtered) == 1
    assert filtered[0].job_id == "job-b"
