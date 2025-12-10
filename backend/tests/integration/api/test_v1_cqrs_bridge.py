"""API integration tests ensuring v1 endpoints surface legacy pipeline data."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.v1 import dependencies
from backend.application.queries.get_extraction_result import GetExtractionResultHandler
from backend.application.queries.get_job_status import GetJobStatusHandler
from backend.legacy.services.store import job_store
from backend.main import app
from backend.tests.integration.application.test_cqrs_legacy_bridge import (
    _run_legacy_pipeline,
)


def _override_dependencies(job_repository, page_repository):
    """Seed dependency overrides with handler instances backed by test repos."""

    overrides = {
        dependencies.get_job_status_handler: lambda: GetJobStatusHandler(job_repository),
        dependencies.get_extraction_result_handler: lambda: GetExtractionResultHandler(job_repository, page_repository),
        dependencies.get_page_repository: lambda: page_repository,
    }
    app.dependency_overrides.update(overrides)
    return overrides


def test_job_status_endpoint_reports_completed_job(tmp_path, monkeypatch) -> None:
    job_id, job_repository, page_repository = _run_legacy_pipeline(tmp_path, monkeypatch)
    overrides = _override_dependencies(job_repository, page_repository)

    response = None
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/jobs/{job_id}/status")
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["jobId"] == job_id
    assert payload["state"] == "completed"
    assert payload["processedPages"] == 1
    assert payload["totalPages"] == 1

    job_store._jobs.clear()


def test_job_page_endpoint_returns_extracted_fields(tmp_path, monkeypatch) -> None:
    job_id, job_repository, page_repository = _run_legacy_pipeline(tmp_path, monkeypatch)
    overrides = _override_dependencies(job_repository, page_repository)

    response = None
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/jobs/{job_id}/pages/1")
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["pageNumber"] == 1
    assert payload["fields"], "expected extracted fields in response"
    assert payload["fields"][0]["name"] == "total_amount"
    assert payload["fields"][0]["value"] == "$123.45"
    assert payload["imageUrl"] == f"/api/jobs/{job_id}/pages/1/image"
    assert payload["documentTypeHint"] == "invoice"
    assert payload["documentTypeConfidence"] == pytest.approx(0.93, rel=1e-2)
    assert payload["tables"] == []

    job_store._jobs.clear()


def test_job_page_image_endpoint_serves_snapshot_asset(tmp_path, monkeypatch) -> None:
    job_id, job_repository, page_repository = _run_legacy_pipeline(tmp_path, monkeypatch)
    overrides = _override_dependencies(job_repository, page_repository)

    response = None
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/jobs/{job_id}/pages/1/image")
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("image/")

    job_store._jobs.clear()