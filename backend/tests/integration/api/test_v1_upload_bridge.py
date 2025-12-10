"""Integration test ensuring upload endpoint bridges to legacy job runner snapshots."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.v1 import dependencies
from backend.application.commands.upload_document import UploadDocumentHandler
from backend.infrastructure.persistence.file_job_repository import FileJobRepository
from backend.legacy.services import history_service, job_runner
from backend.legacy.services.store import job_store
from backend.models.job import PageExtraction
from backend.repositories import snapshot_repository
from backend.main import app


def test_upload_endpoint_creates_snapshot_via_legacy_runner(tmp_path, monkeypatch) -> None:
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

    monkeypatch.setattr(job_runner, "pdf_to_images", fake_pdf_to_images)

    starter_calls: list[str] = []

    def stub_job_starter(job):
        starter_calls.append(job.status.job_id)

    overrides = {
        dependencies.get_upload_document_handler: lambda: UploadDocumentHandler(job_runner.create_job),
        dependencies.get_job_starter: lambda: stub_job_starter,
    }
    app.dependency_overrides.update(overrides)

    try:
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        files = {"file": ("sample.pdf", BytesIO(pdf_bytes), "application/pdf")}

        with TestClient(app) as client:
            response = client.post("/api/upload", files=files)
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 202
    payload = response.json()
    job_id = payload["jobId"]
    assert job_id in starter_calls

    repository = FileJobRepository(base_dir=storage_dir)
    hydrated = repository.find_by_id(job_id)
    assert hydrated is not None
    assert hydrated.total_pages == 1

    job_store._jobs.clear()