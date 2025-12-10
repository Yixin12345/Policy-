"""Query handler for retrieving low-confidence field records."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from backend.application.dto.history_dto import LowConfidenceFieldDTO
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.services.confidence_calculator import ConfidenceCalculator


@dataclass(frozen=True)
class ListLowConfidenceFieldsQuery:
    """Query parameters for low-confidence field retrieval."""

    limit: Optional[int] = 50
    job_id: Optional[str] = None


class ListLowConfidenceFieldsHandler:
    """Handles extraction of low-confidence fields across jobs."""

    def __init__(self, job_repository: JobRepository, confidence_calculator: ConfidenceCalculator | None = None):
        self._jobs = job_repository
        self._confidence = confidence_calculator or ConfidenceCalculator()

    def handle(self, query: ListLowConfidenceFieldsQuery) -> List[LowConfidenceFieldDTO]:
        limit = query.limit
        if limit is not None and limit <= 0:
            return []

        results: List[LowConfidenceFieldDTO] = []
        for job in self._jobs.find_all():
            if query.job_id and job.job_id != query.job_id:
                continue

            document_name = job.filename or job.job_id
            low_conf_fields = self._confidence.extract_low_confidence_fields(job.pages)
            for field in low_conf_fields:
                confidence_value = float(field.get("confidence", 0.0))
                results.append(
                    LowConfidenceFieldDTO(
                        job_id=job.job_id,
                        document_name=document_name,
                        page=int(field.get("page", 0)),
                        name=str(field.get("name", "")),
                        value=str(field.get("value", "")),
                        confidence=confidence_value,
                    )
                )

        results.sort(key=lambda item: (item.confidence, item.job_id, item.page, item.name))

        if limit is None:
            return results
        return results[:limit]
