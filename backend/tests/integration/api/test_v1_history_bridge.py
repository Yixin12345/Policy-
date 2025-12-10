"""API history endpoint tests backed by legacy-generated snapshots."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.v1 import dependencies
from backend.application.queries.get_history_job_detail import GetHistoryJobDetailHandler
from backend.application.queries.get_history_metrics import GetHistoryMetricsHandler
from backend.application.queries.list_history_jobs import ListHistoryJobsHandler
from backend.application.queries.list_low_confidence_fields import ListLowConfidenceFieldsHandler
from backend.domain.services.confidence_calculator import ConfidenceCalculator
from backend.legacy.services import history_service
from backend.legacy.services.store import job_store
from backend.main import app
from backend.tests.integration.application.test_cqrs_legacy_bridge import _run_legacy_pipeline


def _override_history_dependencies(job_repository, page_repository):
    overrides = {
        dependencies.get_job_repository: lambda: job_repository,
        dependencies.get_page_repository: lambda: page_repository,
        dependencies.get_list_history_jobs_handler: lambda: ListHistoryJobsHandler(job_repository, ConfidenceCalculator()),
        dependencies.get_history_metrics_handler: lambda: GetHistoryMetricsHandler(job_repository),
        dependencies.get_low_confidence_fields_handler: lambda: ListLowConfidenceFieldsHandler(job_repository, ConfidenceCalculator()),
        dependencies.get_history_job_detail_handler: lambda: GetHistoryJobDetailHandler(dependencies._load_history_job),
    }
    app.dependency_overrides.update(overrides)
    return overrides


def _ensure_aggregated_payload(job_id: str) -> None:
    job = job_store.get(job_id)
    if not job:
        return
    aggregated = job.aggregated or {}
    if "jobId" not in aggregated or "fields" not in aggregated:
        job.aggregated = {
            "jobId": job.status.job_id,
            "fields": aggregated.get("fields", []),
        }
    job_store.update(job_id, job)
    history_service.save_job_snapshot(job)


def test_history_jobs_list_includes_legacy_job(tmp_path, monkeypatch) -> None:
    job_id, job_repository, page_repository = _run_legacy_pipeline(tmp_path, monkeypatch)
    _ensure_aggregated_payload(job_id)
    overrides = _override_history_dependencies(job_repository, page_repository)

    try:
        with TestClient(app) as client:
            response = client.get("/api/history/jobs")
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    payload = response.json()
    job_ids = {job["jobId"] for job in payload.get("jobs", [])}
    assert job_id in job_ids

    job_store._jobs.clear()


def test_history_job_detail_returns_pages(tmp_path, monkeypatch) -> None:
    job_id, job_repository, page_repository = _run_legacy_pipeline(tmp_path, monkeypatch)
    _ensure_aggregated_payload(job_id)
    overrides = _override_history_dependencies(job_repository, page_repository)

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/history/jobs/{job_id}")
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["jobId"] == job_id
    assert payload["pages"], "expected at least one page in history detail"

    job_store._jobs.clear()


def test_history_metrics_endpoint_returns_counts(tmp_path, monkeypatch) -> None:
    job_id, job_repository, page_repository = _run_legacy_pipeline(tmp_path, monkeypatch)
    _ensure_aggregated_payload(job_id)
    overrides = _override_history_dependencies(job_repository, page_repository)

    try:
        with TestClient(app) as client:
            response = client.get("/api/history/metrics")
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    payload = response.json()
    assert "week" in payload and "month" in payload and "year" in payload

    job_store._jobs.clear()


def test_history_low_confidence_endpoint_returns_list(tmp_path, monkeypatch) -> None:
    job_id, job_repository, page_repository = _run_legacy_pipeline(tmp_path, monkeypatch)
    _ensure_aggregated_payload(job_id)
    overrides = _override_history_dependencies(job_repository, page_repository)

    try:
        with TestClient(app) as client:
            response = client.get("/api/history/low-confidence")
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)

    job_store._jobs.clear()