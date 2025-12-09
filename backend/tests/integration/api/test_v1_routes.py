"""Integration smoke tests for the v1 API routers.

These tests ensure that the new FastAPI routers can successfully serve
responses using the real dependency graph (for read endpoints) and with
lightweight overrides for the upload workflow. They provide quick evidence
that the wiring performed in Day 11 is functional before the infrastructure
refactors begin.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.application.dto.canonical_dto import CanonicalBundleDTO
from backend.main import app
from backend.api.v1 import dependencies
from backend.models.job import ExtractionJob, JobStatus, PageExtraction

SAMPLE_JOB_ID = "0142bcf4e1734e3cb472636ca4088de0"
SAMPLE_PAGE_NUMBER = 1


@pytest.fixture(autouse=True)
def reset_dependency_overrides():
    """Ensure dependency overrides do not leak between tests."""
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_get_job_status_returns_snapshot(client: TestClient) -> None:
    response = client.get(f"/api/jobs/{SAMPLE_JOB_ID}/status")
    assert response.status_code == 200

    payload = response.json()
    assert payload["jobId"] == SAMPLE_JOB_ID
    assert payload["totalPages"] >= 1
    assert payload["state"]


def test_get_job_page_returns_fields(client: TestClient) -> None:
    response = client.get(f"/api/jobs/{SAMPLE_JOB_ID}/pages/{SAMPLE_PAGE_NUMBER}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["pageNumber"] == SAMPLE_PAGE_NUMBER
    assert isinstance(payload["fields"], list)


def test_get_job_page_image_serves_file(client: TestClient) -> None:
    response = client.get(f"/api/jobs/{SAMPLE_JOB_ID}/pages/{SAMPLE_PAGE_NUMBER}/image")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "image" in content_type


def test_get_job_aggregated_results_returns_stats(client: TestClient) -> None:
    response = client.get(f"/api/jobs/{SAMPLE_JOB_ID}/aggregated")
    assert response.status_code == 200

    payload = response.json()
    assert payload["jobId"] == SAMPLE_JOB_ID
    assert isinstance(payload["fields"], list)


def test_get_job_canonical_returns_bundle(client: TestClient) -> None:
    class _StubCanonicalHandler:
        def handle(self, query):  # noqa: ANN001 - FastAPI passes query object
            assert query.job_id == SAMPLE_JOB_ID
            return CanonicalBundleDTO(
                job_id=query.job_id,
                canonical={
                    "invoice": {
                        "Policy number": {
                            "value": "12345",
                            "confidence": 0.97,
                            "sources": [{"page": 1, "fieldId": "field-1"}],
                        }
                    }
                },
                trace={"model": "stub"},
                document_categories=["INVOICE"],
                document_types=["INVOICE"],
                page_categories={1: "invoice"},
                page_classifications=[{"page": 1, "label": "invoice", "confidence": 0.9}],
            )

    app.dependency_overrides[dependencies.get_canonical_bundle_handler] = lambda: _StubCanonicalHandler()

    response = client.get(f"/api/jobs/{SAMPLE_JOB_ID}/canonical")
    assert response.status_code == 200

    payload = response.json()
    assert payload["jobId"] == SAMPLE_JOB_ID
    assert payload["documentCategories"] == ["INVOICE"]
    assert payload["canonical"]["invoice"]["Policy number"]["value"] == "12345"


def test_list_history_jobs_returns_entries(client: TestClient) -> None:
    response = client.get("/api/history/jobs")
    assert response.status_code == 200

    payload = response.json()
    assert "jobs" in payload
    assert isinstance(payload["jobs"], list)


def test_get_history_job_returns_detail(client: TestClient) -> None:
    response = client.get(f"/api/history/jobs/{SAMPLE_JOB_ID}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["jobId"] == SAMPLE_JOB_ID
    assert "pages" in payload


def test_get_history_metrics_returns_time_windows(client: TestClient) -> None:
    response = client.get("/api/history/metrics")
    assert response.status_code == 200

    payload = response.json()
    assert "week" in payload
    assert "month" in payload
    assert "year" in payload


def test_list_low_confidence_fields_returns_records(client: TestClient) -> None:
    response = client.get("/api/history/low-confidence")
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)


class _StubUploadHandler:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.seen = []

    def handle(self, command):
        self.seen.append(command)
        return ExtractionJob(
            status=JobStatus(job_id="upload-job", total_pages=1),
            pdf_path=command.file_path,
            output_dir=self.output_dir,
            pages=[PageExtraction(page_number=1)],
        )


class _StubJobStarter:
    def __init__(self):
        self.jobs = []

    def __call__(self, job: ExtractionJob) -> None:
        self.jobs.append(job)


def test_upload_document_accepts_pdf(tmp_path: Path, client: TestClient) -> None:
    handler = _StubUploadHandler(output_dir=tmp_path)
    starter = _StubJobStarter()

    app.dependency_overrides[dependencies.get_upload_document_handler] = lambda: handler
    app.dependency_overrides[dependencies.get_job_starter] = lambda: starter

    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    files = {"file": ("sample.pdf", BytesIO(pdf_bytes), "application/pdf")}

    response = client.post("/api/upload", files=files)
    assert response.status_code == 202

    payload = response.json()
    assert payload["jobId"] == "upload-job"
    assert handler.seen, "upload handler did not receive command"
    assert starter.jobs, "job starter was not invoked"


