"""Query handler for dashboard history metrics."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from backend.application.dto.history_dto import DashboardMetricsDTO, TimeWindowMetricsDTO
from backend.domain.entities.job import Job
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.value_objects.job_status import JobState


@dataclass(frozen=True)
class GetHistoryMetricsQuery:
    """Query describing the point-in-time for computing dashboard metrics."""

    as_of: datetime | None = None


class GetHistoryMetricsHandler:
    """Handles calculation of dashboard metrics across rolling windows."""

    def __init__(self, job_repository: JobRepository):
        self._jobs = job_repository

    def handle(self, query: GetHistoryMetricsQuery) -> DashboardMetricsDTO:
        """Compute metrics for predefined rolling windows."""
        as_of = query.as_of or datetime.now(timezone.utc)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        else:
            as_of = as_of.astimezone(timezone.utc)

        jobs = self._jobs.find_all()
        windows = {
            "week": as_of - timedelta(days=7),
            "month": as_of - timedelta(days=30),
            "year": as_of - timedelta(days=365),
        }

        metrics = {
            name: self._compute_window_metrics(jobs, cutoff)
            for name, cutoff in windows.items()
        }

        return DashboardMetricsDTO(
            week=metrics["week"],
            month=metrics["month"],
            year=metrics["year"],
        )

    def _compute_window_metrics(self, jobs: Iterable[Job], cutoff: datetime) -> TimeWindowMetricsDTO:
        total_jobs = 0
        total_pages = 0
        total_fields = 0
        total_tables = 0
        total_processing_ms = 0

        for job in jobs:
            finished_at = self._job_finished_at(job)
            if finished_at is None or finished_at < cutoff:
                continue

            total_jobs += 1
            total_pages += job.total_pages or len(job.pages)
            total_fields += sum(len(page.fields) for page in job.pages)
            total_tables += sum(len(page.tables) for page in job.pages)

            duration_ms = self._calculate_processing_ms(job)
            if duration_ms is not None:
                total_processing_ms += duration_ms

        return TimeWindowMetricsDTO(
            total_jobs=total_jobs,
            total_pages=total_pages,
            total_fields=total_fields,
            total_tables=total_tables,
            total_processing_ms=total_processing_ms if total_processing_ms > 0 else None,
        )

    @staticmethod
    def _job_finished_at(job: Job) -> datetime | None:
        if job.status.state not in {JobState.COMPLETED, JobState.PARTIAL, JobState.ERROR, JobState.CANCELLED}:
            return None

        timestamp = job.updated_at or job.created_at
        if timestamp is None:
            return None
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    @staticmethod
    def _calculate_processing_ms(job: Job) -> int | None:
        if job.created_at is None or job.updated_at is None:
            return None
        start = job.created_at
        end = job.updated_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        duration = end - start
        if duration.total_seconds() < 0:
            return None
        return int(duration.total_seconds() * 1000)
