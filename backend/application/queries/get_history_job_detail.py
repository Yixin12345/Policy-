"""Query handler for retrieving detailed history job information."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.domain.exceptions import EntityNotFoundError
from backend.models.job import ExtractionJob


JobLoader = Callable[[str], ExtractionJob | None]


@dataclass(frozen=True)
class GetHistoryJobDetailQuery:
    """Query describing the job to load for history detail view."""

    job_id: str


class GetHistoryJobDetailHandler:
    """Load persisted job detail records for history routes."""

    def __init__(self, loader: JobLoader):
        self._loader = loader

    def handle(self, query: GetHistoryJobDetailQuery) -> ExtractionJob:
        job = self._loader(query.job_id)
        if job is None:
            raise EntityNotFoundError("job", query.job_id)
        return job
