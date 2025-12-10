"""Query handler for listing job history summaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from backend.application.dto.history_dto import HistoryJobSummaryDTO
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.services.confidence_calculator import ConfidenceCalculator


@dataclass(frozen=True)
class ListHistoryJobsQuery:
    """Query describing pagination options for history listing."""

    limit: int = 50
    offset: int = 0


class ListHistoryJobsHandler:
    """Handles retrieval of job history summaries."""

    def __init__(self, job_repository: JobRepository, confidence_calculator: ConfidenceCalculator | None = None):
        self._jobs = job_repository
        self._confidence = confidence_calculator or ConfidenceCalculator()

    def handle(self, query: ListHistoryJobsQuery) -> List[HistoryJobSummaryDTO]:
        jobs = self._jobs.find_all(limit=query.limit, offset=query.offset)
        summaries: List[HistoryJobSummaryDTO] = []

        for job in jobs:
            total_pages = job.total_pages or len(job.pages)
            total_fields = sum(len(page.fields) for page in job.pages)
            total_tables = sum(len(page.tables) for page in job.pages)

            stats = self._confidence.calculate_page_statistics(job.pages)
            total_processing_ms = self._calculate_processing_ms(job)

            summaries.append(
                HistoryJobSummaryDTO(
                    job_id=job.job_id,
                    document_name=job.filename,
                    status=job.status.state.value,
                    total_pages=total_pages or 0,
                    total_fields=total_fields,
                    total_tables=total_tables,
                    low_confidence_count=stats.low_confidence_count,
                    confidence_buckets=list(stats.buckets),
                    total_processing_ms=total_processing_ms,
                    started_at=job.created_at,
                    finished_at=job.updated_at,
                    last_modified=job.updated_at,
                )
            )

        return summaries

    @staticmethod
    def _calculate_processing_ms(job) -> int | None:
        if job.created_at is None or job.updated_at is None:
            return None
        duration = job.updated_at - job.created_at
        if duration.total_seconds() < 0:
            return None
        return int(duration.total_seconds() * 1000)
