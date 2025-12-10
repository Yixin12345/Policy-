"""Integration tests exercising CQRS handlers against legacy pipeline output."""

from __future__ import annotations

from pathlib import Path

from backend.application.queries.get_extraction_result import (
    GetExtractionResultHandler,
    GetExtractionResultQuery,
)
from backend.application.queries.get_job_status import (
    GetJobStatusHandler,
    GetJobStatusQuery,
)
from backend.domain.value_objects.job_status import JobState
from backend.infrastructure.persistence.file_job_repository import FileJobRepository
from backend.infrastructure.persistence.file_page_repository import FilePageRepository
from backend.legacy.services import history_service, job_runner
from backend.legacy.services.store import job_store
from backend.models.job import FieldExtraction, PageExtraction
from backend.repositories import snapshot_repository


def _run_legacy_pipeline(tmp_path, monkeypatch):
    """Execute the legacy job runner with faked dependencies and return repo + job id."""
    storage_dir = tmp_path / "snapshots"

    monkeypatch.setattr(history_service, "BASE_STORAGE_DIR", storage_dir)
    monkeypatch.setattr(snapshot_repository, "BASE_STORAGE_DIR", storage_dir)
    monkeypatch.setattr(job_runner, "BASE_OUTPUT_DIR", storage_dir)

    storage_dir.mkdir(parents=True, exist_ok=True)
    job_runner.BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    job_store._jobs.clear()

    def fake_pdf_to_images(pdf_path: Path, target_dir: Path):
        target_dir.mkdir(parents=True, exist_ok=True)
        image_path = target_dir / "page-1.png"
        image_path.write_bytes(b"fake-image")
        return [PageExtraction(page_number=1, status="pending", image_path=image_path)]

    def fake_call_vision_model(image_path: str, page_number: int):  # noqa: ARG001 - signature parity
        return {
            "documentType": {
                "label": "invoice",
                "confidence": 0.93,
                "reasons": ["total present"],
            }
        }

    def fake_parse_fields(page_number: int, payload: dict):  # noqa: ARG001 - signature parity
        return [
            FieldExtraction(
                id="field-1",
                page=page_number,
                name="total_amount",
                value="$123.45",
                confidence=0.95,
            )
        ]

    def fake_parse_tables(page_number: int, payload: dict):  # noqa: ARG001 - signature parity
        return []

    monkeypatch.setattr(job_runner, "pdf_to_images", fake_pdf_to_images)
    monkeypatch.setattr(job_runner, "call_vision_model", fake_call_vision_model)
    monkeypatch.setattr(job_runner, "parse_fields", fake_parse_fields)
    monkeypatch.setattr(job_runner, "parse_tables", fake_parse_tables)
    monkeypatch.setattr(job_runner, "aggregate_fields", lambda job: {"fieldCount": len(job.pages or [])})
    monkeypatch.setattr(job_runner.table_grouping, "assign_table_groups", lambda pages: {})
    monkeypatch.setattr(job_runner.table_grouping, "merge_table_segments", lambda groups: {})
    monkeypatch.setattr(job_runner, "generate_canonical_bundle", lambda job: ({"documentTypes": ["Invoice"]}, {"steps": []}))

    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%EOF")

    job = job_runner.create_job(pdf_path, "uploaded.pdf")

    job_runner._process_job(job.status.job_id)

    repository = FileJobRepository(base_dir=storage_dir)
    page_repository = FilePageRepository(repository)

    return job.status.job_id, repository, page_repository


def test_get_job_status_reads_completed_legacy_job(tmp_path, monkeypatch) -> None:
    job_id, job_repository, _ = _run_legacy_pipeline(tmp_path, monkeypatch)

    handler = GetJobStatusHandler(job_repository)
    dto = handler.handle(GetJobStatusQuery(job_id))

    assert dto.job_id == job_id
    assert dto.status == JobState.COMPLETED.value
    assert dto.total_pages == 1
    assert dto.processed_pages == 1
    assert dto.progress == 1.0

    job_store._jobs.clear()


def test_get_extraction_result_returns_domain_page_data(tmp_path, monkeypatch) -> None:
    job_id, job_repository, page_repository = _run_legacy_pipeline(tmp_path, monkeypatch)

    handler = GetExtractionResultHandler(job_repository, page_repository)
    result = handler.handle(GetExtractionResultQuery(job_id=job_id, page_number=1))

    assert result.job_id == job_id
    assert result.page_number == 1
    assert result.form_fields
    assert result.form_fields[0].name == "total_amount"
    assert result.confidence_score > 0

    job_store._jobs.clear()