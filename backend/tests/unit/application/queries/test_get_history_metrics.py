"""Unit tests for GetHistoryMetricsHandler."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pytest

from backend.application.queries.get_history_metrics import GetHistoryMetricsHandler, GetHistoryMetricsQuery
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.value_objects.job_status import JobStatus


class StubJobRepository(JobRepository):
    """In-memory repository for testing history metrics."""

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


def make_job(job_id: str, created_at: datetime, updated_at: datetime, fields: int, pages: int) -> Job:
    page_list = []
    for page_number in range(1, pages + 1):
        page_fields = [
            FieldExtraction.create(
                field_name=f"field-{page_number}-{index}",
                value="value",
                confidence=0.5,
            )
            for index in range(fields)
        ]
        page_list.append(PageExtraction.create(page_number=page_number, fields=page_fields))

    return Job(
        job_id=job_id,
        filename=f"{job_id}.pdf",
        status=JobStatus.completed(),
        total_pages=pages,
        pages=page_list,
        created_at=created_at,
        updated_at=updated_at,
        source_path=None,
    )


def test_metrics_exclude_non_terminal_jobs():
    as_of = datetime(2024, 1, 10, tzinfo=timezone.utc)
    recent_created = as_of - timedelta(days=2, hours=2)
    recent_finished = as_of - timedelta(days=2)
    recent_job = make_job("recent", recent_created, recent_finished, fields=3, pages=2)

    old_created = as_of - timedelta(days=50, hours=1)
    old_finished = as_of - timedelta(days=50)
    old_job = make_job("old", old_created, old_finished, fields=2, pages=1)

    active_created = as_of - timedelta(days=1)
    active_job = Job(
        job_id="active",
        filename="active.pdf",
        status=JobStatus.running(0.5),
        total_pages=1,
        pages=[PageExtraction.create(page_number=1)],
        created_at=active_created,
        updated_at=active_created,
        source_path=None,
    )

    repository = StubJobRepository([recent_job, old_job, active_job])
    handler = GetHistoryMetricsHandler(repository)
    metrics = handler.handle(GetHistoryMetricsQuery(as_of=as_of))

    assert metrics.week.total_jobs == 1
    assert metrics.week.total_pages == 2
    assert metrics.week.total_fields == 6
    assert metrics.week.total_tables == 0
    assert metrics.week.total_processing_ms == int((recent_finished - recent_created).total_seconds() * 1000)

    assert metrics.month.total_jobs == 1  # Old job falls outside 30-day window
    assert metrics.year.total_jobs == 2
    assert metrics.year.total_fields == 6 + 2
    assert metrics.year.total_processing_ms == int((recent_finished - recent_created).total_seconds() * 1000) + int((old_finished - old_created).total_seconds() * 1000)


@pytest.mark.parametrize("limit_days,expected", [(7, 1), (365, 1)])
def test_metrics_window_boundaries(limit_days: int, expected: int):
    as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
    job = make_job(
        "job",
        created_at=as_of - timedelta(days=limit_days - 1, hours=1),
        updated_at=as_of - timedelta(days=limit_days - 1),
        fields=1,
        pages=1,
    )
    repository = StubJobRepository([job])
    handler = GetHistoryMetricsHandler(repository)
    metrics = handler.handle(GetHistoryMetricsQuery(as_of=as_of))

    if limit_days == 7:
        assert metrics.week.total_jobs == expected
    else:
        assert metrics.year.total_jobs == expected
