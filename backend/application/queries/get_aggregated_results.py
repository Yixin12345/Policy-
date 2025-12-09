"""Query handler for aggregated job results."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, List

from backend.application.dto.job_dto import (
    AggregatedFieldDTO,
    AggregatedFieldValueDTO,
    AggregatedResultsDTO,
)
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.exceptions import EntityNotFoundError
from backend.domain.repositories.job_repository import JobRepository


@dataclass(frozen=True)
class GetAggregatedResultsQuery:
    """Query describing which job's aggregated results to retrieve."""

    job_id: str


class GetAggregatedResultsHandler:
    """Compute aggregated field data for a job using domain entities."""

    def __init__(self, job_repository: JobRepository):
        self._jobs = job_repository

    def handle(self, query: GetAggregatedResultsQuery) -> AggregatedResultsDTO:
        job = self._jobs.find_by_id(query.job_id)
        if job is None:
            raise EntityNotFoundError("job", query.job_id)

        aggregated_fields = self._aggregate_fields(job.pages)
        return AggregatedResultsDTO(job_id=job.job_id, fields=aggregated_fields)

    def _aggregate_fields(self, pages: List[PageExtraction]) -> List[AggregatedFieldDTO]:
        bucket: Dict[str, List[AggregatedFieldValueDTO]] = {}
        field_names: Dict[str, str] = {}

        for page in pages:
            for field in page.fields:
                key = field.field_name.strip().lower()
                value_dto = AggregatedFieldValueDTO(
                    page=page.page_number,
                    value=field.value,
                    confidence=field.confidence.value,
                )
                bucket.setdefault(key, []).append(value_dto)
                field_names.setdefault(key, field.field_name)

        aggregated: List[AggregatedFieldDTO] = []
        for key, values in bucket.items():
            pages_with_field = sorted({value.page for value in values})
            best = max(values, key=lambda item: item.confidence if item.confidence is not None else 0.0)
            confidences = [value.confidence for value in values]
            stats = {
                "min": min(confidences) if confidences else 0.0,
                "max": max(confidences) if confidences else 0.0,
                "avg": mean(confidences) if confidences else 0.0,
            }
            aggregated.append(
                AggregatedFieldDTO(
                    canonical_name=field_names.get(key, key),
                    pages=pages_with_field,
                    values=values,
                    best_value=best.value,
                    confidence_stats=stats,
                )
            )

        aggregated.sort(key=lambda item: item.canonical_name)
        return aggregated
