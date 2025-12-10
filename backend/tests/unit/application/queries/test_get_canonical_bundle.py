from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from backend.application.dto.canonical_dto import CanonicalBundleDTO
from backend.application.queries.get_canonical_bundle import (
    GetCanonicalBundleHandler,
    GetCanonicalBundleQuery,
)
from backend.domain.entities.job import Job
from backend.domain.exceptions import EntityNotFoundError
from backend.domain.repositories.job_repository import JobRepository
from backend.infrastructure.mapping.azure_mapping_client import MappingResult
from backend.models.job import ExtractionJob, JobStatus, PageExtraction


class StubJobRepository(JobRepository):
    def __init__(self, job: Optional[Job] = None) -> None:
        self._job = job

    def save(self, job: Job) -> None:  # pragma: no cover - not needed for tests
        self._job = job

    def find_by_id(self, job_id: str) -> Optional[Job]:
        if self._job and self._job.job_id == job_id:
            return self._job
        return None

    def find_all(self, limit: Optional[int] = None, offset: int = 0, sort_desc: bool = True):  # pragma: no cover - unused
        return []

    def find_by_status(self, status: str, limit: Optional[int] = None, offset: int = 0, sort_desc: bool = True):  # pragma: no cover - unused
        return []

    def delete(self, job_id: str) -> bool:  # pragma: no cover - unused
        return False

    def exists(self, job_id: str) -> bool:  # pragma: no cover - unused
        return self._job is not None and self._job.job_id == job_id

    def count(self, status: Optional[str] = None) -> int:  # pragma: no cover - unused
        return 1 if self._job else 0


class StubMappingClient:
    def __init__(self, response: MappingResult) -> None:
        self._response = response
        self.calls: list[Dict[str, Any]] = []

    def generate(
        self,
        job: Job,
        *,
        aggregated: Optional[Dict[str, Any]] = None,
        table_groups: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MappingResult:
        self.calls.append(
            {
                "job": job,
                "aggregated": aggregated,
                "table_groups": table_groups,
                "metadata": metadata,
            }
        )
        return self._response


def build_legacy_job(job_id: str) -> ExtractionJob:
    status = JobStatus(job_id=job_id, total_pages=1, state="completed")
    page = PageExtraction(page_number=1, status="completed")
    job = ExtractionJob(
        status=status,
        pdf_path=Path("/tmp/source.pdf"),
        output_dir=Path("/tmp/output"),
        pages=[page],
    )
    job.metadata.update(
        {
            "documentCategories": ["Invoice"],
            "documentTypes": ["facility_invoice"],
            "pageCategories": {1: "invoice"},
            "pageClassifications": [
                {"page": 1, "label": "invoice", "confidence": 0.92},
            ],
            "tableGroups": {"primary": {"pages": [1], "rowCount": 3, "columns": ["revenueCode"]}},
        }
    )
    job.aggregated = {"fields": []}
    job.document_type = "invoice"
    return job


@pytest.fixture()
def job() -> Job:
    base = Job.create(job_id="job-123", filename="invoice.pdf")
    return base


def test_handle_returns_canonical_dto(job: Job) -> None:
    canonical_payload = {
        "schemaVersion": "1.0.0",
        "documentCategories": ["INVOICE"],
        "documentTypes": ["INVOICE"],
        "invoice": {
            "Policy number": {"value": "12345", "confidence": 0.98, "sources": []},
        },
        "reasoningNotes": ["High confidence"],
    }
    mapping_result = MappingResult(canonical=canonical_payload, trace={"model": "gpt"})
    mapping_client = StubMappingClient(mapping_result)
    repository = StubJobRepository(job)

    handler = GetCanonicalBundleHandler(
        repository,
        mapping_client,
        history_loader=lambda job_id: build_legacy_job(job_id),
    )

    dto = handler.handle(GetCanonicalBundleQuery(job_id=job.job_id))

    assert isinstance(dto, CanonicalBundleDTO)
    assert dto.canonical == canonical_payload
    assert dto.trace == {"model": "gpt"}
    assert dto.document_categories == ["INVOICE"]
    assert dto.document_types == ["INVOICE", "facility_invoice"]
    assert dto.page_categories == {1: "invoice"}
    assert dto.page_classifications == [{"page": 1, "label": "invoice", "confidence": 0.92}]

    assert mapping_client.calls, "Mapping client should be invoked"
    recorded = mapping_client.calls[0]
    assert recorded["aggregated"] == {"fields": []}
    assert recorded["table_groups"] == {"primary": {"pages": [1], "rowCount": 3, "columns": ["revenueCode"]}}
    assert recorded["metadata"] is not None
    assert recorded["metadata"].get("documentType") == "invoice"


def test_handle_without_legacy_context(job: Job) -> None:
    canonical_payload = {"documentCategories": [], "documentTypes": [], "invoice": {}}
    mapping_result = MappingResult(canonical=canonical_payload, trace=None)
    mapping_client = StubMappingClient(mapping_result)
    repository = StubJobRepository(job)

    handler = GetCanonicalBundleHandler(repository, mapping_client, history_loader=lambda job_id: None)

    dto = handler.handle(GetCanonicalBundleQuery(job_id=job.job_id))

    assert dto.document_categories == []
    assert dto.page_categories == {}
    assert dto.page_classifications == []
    assert mapping_client.calls[0]["metadata"] is None


def test_handle_raises_when_job_missing() -> None:
    handler = GetCanonicalBundleHandler(StubJobRepository(), StubMappingClient(MappingResult(canonical={}, trace=None)))

    with pytest.raises(EntityNotFoundError):
        handler.handle(GetCanonicalBundleQuery(job_id="missing"))
