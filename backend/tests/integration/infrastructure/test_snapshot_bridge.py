"""Integration tests bridging legacy snapshots with the domain repository."""

from __future__ import annotations

from pathlib import Path

from backend.domain.value_objects.job_status import JobState
from backend.infrastructure.persistence.file_job_repository import FileJobRepository
from backend.legacy.services import history_service, job_runner
from backend.legacy.services.store import job_store
from backend.models.job import FieldExtraction, PageExtraction
from backend.repositories import snapshot_repository


def test_legacy_job_creation_writes_snapshot_for_domain_repo(tmp_path, monkeypatch) -> None:
    """Ensure legacy job creation emits a snapshot readable by the domain repository."""
    storage_dir = tmp_path / "snapshots"
    output_dir = tmp_path / "output"

    monkeypatch.setattr(history_service, "BASE_STORAGE_DIR", storage_dir)
    monkeypatch.setattr(snapshot_repository, "BASE_STORAGE_DIR", storage_dir)
    monkeypatch.setattr(job_runner, "BASE_OUTPUT_DIR", output_dir)

    storage_dir.mkdir(parents=True, exist_ok=True)
    job_runner.BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    job_store._jobs.clear()  # reset singleton between tests

    def fake_pdf_to_images(pdf_path: Path, target_dir: Path):
        target_dir.mkdir(parents=True, exist_ok=True)
        image_path = target_dir / "page-1.png"
        image_path.write_bytes(b"fake-image")
        return [PageExtraction(page_number=1, status="pending", image_path=image_path)]

    monkeypatch.setattr(job_runner, "pdf_to_images", fake_pdf_to_images)

    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%EOF")

    job = job_runner.create_job(pdf_path, "uploaded.pdf")

    repository = FileJobRepository(base_dir=storage_dir)
    hydrated = repository.find_by_id(job.status.job_id)

    assert hydrated is not None
    assert hydrated.job_id == job.status.job_id
    assert hydrated.filename == "uploaded.pdf"
    assert hydrated.status.state == JobState.QUEUED
    assert hydrated.total_pages == 1

    job_store._jobs.clear()


def test_legacy_job_processing_updates_snapshot_for_domain_repo(tmp_path, monkeypatch) -> None:
    """Ensure full legacy processing lifecycle updates the snapshot for domain consumers."""
    storage_dir = tmp_path / "snapshots"
    output_dir = tmp_path / "output"

    monkeypatch.setattr(history_service, "BASE_STORAGE_DIR", storage_dir)
    monkeypatch.setattr(snapshot_repository, "BASE_STORAGE_DIR", storage_dir)
    monkeypatch.setattr(job_runner, "BASE_OUTPUT_DIR", output_dir)

    storage_dir.mkdir(parents=True, exist_ok=True)
    job_runner.BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    job_store._jobs.clear()

    def fake_pdf_to_images(pdf_path: Path, target_dir: Path):
        target_dir.mkdir(parents=True, exist_ok=True)
        image_path = target_dir / "page-1.png"
        image_path.write_bytes(b"fake-image")
        return [PageExtraction(page_number=1, status="pending", image_path=image_path)]

    def fake_call_vision_model(image_path: str, page_number: int):  # noqa: ARG001 - keep legacy signature
        return {
            "documentType": {
                "label": "invoice",
                "confidence": 0.93,
                "reasons": ["total present"],
            }
        }

    def fake_parse_fields(page_number: int, payload: dict):  # noqa: ARG001 - keep legacy signature
        return [
            FieldExtraction(
                id="field-1",
                page=page_number,
                name="total_amount",
                value="$123.45",
                confidence=0.95,
            )
        ]

    def fake_parse_tables(page_number: int, payload: dict):  # noqa: ARG001 - keep legacy signature
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
    hydrated = repository.find_by_id(job.status.job_id)

    assert hydrated is not None
    assert hydrated.status.state == JobState.COMPLETED
    assert hydrated.pages
    assert hydrated.pages[0].has_fields
    assert hydrated.pages[0].fields[0].field_name == "total_amount"

    job_store._jobs.clear()