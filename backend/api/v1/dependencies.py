"""Shared FastAPI dependencies for v1 API routers.

These factories centralize construction of repositories and legacy services so
routers can depend on simple callables. Keeping object creation here makes it
straightforward to swap implementations once the legacy stack is fully
replaced.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Callable

from backend.application.commands.delete_job import DeleteJobHandler
from backend.application.commands.save_edits import SaveEditsHandler
from backend.application.commands.upload_document import UploadDocumentHandler
from backend.application.queries.get_aggregated_results import GetAggregatedResultsHandler
from backend.application.queries.get_canonical_bundle import GetCanonicalBundleHandler
from backend.application.queries.get_extraction_result import GetExtractionResultHandler
from backend.application.queries.get_history_job_detail import GetHistoryJobDetailHandler
from backend.application.queries.get_history_metrics import GetHistoryMetricsHandler
from backend.application.queries.get_job_status import GetJobStatusHandler
from backend.application.queries.list_history_jobs import ListHistoryJobsHandler
from backend.application.queries.list_low_confidence_fields import ListLowConfidenceFieldsHandler
from backend.legacy.services.history_service import load_job_from_snapshot
from backend.legacy.services.job_runner import create_job, get_job
from backend.legacy.services.markdown_job_runner import create_markdown_job
from backend.legacy.services.processing_dispatcher import start_job_processing
from backend.legacy.services.store import job_store
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.repositories.page_repository import PageRepository
from backend.domain.services.confidence_calculator import ConfidenceCalculator
from backend.infrastructure.persistence.file_job_repository import FileJobRepository
from backend.infrastructure.mapping.azure_mapping_client import AzureMappingClient
from backend.infrastructure.persistence.file_page_repository import (
    FilePageRepository,
)


@lru_cache()
def _job_repository() -> JobRepository:
    return FileJobRepository()


def get_job_repository() -> JobRepository:
    """Provide a singleton job repository instance."""
    return _job_repository()


@lru_cache()
def _page_repository() -> PageRepository:
    return FilePageRepository(_job_repository())


def get_page_repository() -> PageRepository:
    """Provide a singleton page repository instance."""
    return _page_repository()


@lru_cache()
def _get_job_status_handler() -> GetJobStatusHandler:
    return GetJobStatusHandler(_job_repository())


def get_job_status_handler() -> GetJobStatusHandler:
    """Provide a cached GetJobStatus handler."""
    return _get_job_status_handler()


@lru_cache()
def _get_extraction_result_handler() -> GetExtractionResultHandler:
    return GetExtractionResultHandler(_job_repository(), _page_repository())


def get_extraction_result_handler() -> GetExtractionResultHandler:
    """Provide a cached GetExtractionResult handler."""
    return _get_extraction_result_handler()


@lru_cache()
def _get_save_edits_handler() -> SaveEditsHandler:
    return SaveEditsHandler(_job_repository(), _page_repository())


def get_save_edits_handler() -> SaveEditsHandler:
    """Provide a cached SaveEdits handler."""
    return _get_save_edits_handler()


@lru_cache()
def _get_delete_job_handler() -> DeleteJobHandler:
    return DeleteJobHandler(_job_repository())


def get_delete_job_handler() -> DeleteJobHandler:
    """Provide a cached DeleteJob handler."""
    return _get_delete_job_handler()


@lru_cache()
def _confidence_calculator() -> ConfidenceCalculator:
    return ConfidenceCalculator()


@lru_cache()
def _get_list_history_jobs_handler() -> ListHistoryJobsHandler:
    return ListHistoryJobsHandler(_job_repository(), _confidence_calculator())


def get_list_history_jobs_handler() -> ListHistoryJobsHandler:
    """Provide a cached history listing handler."""
    return _get_list_history_jobs_handler()


@lru_cache()
def _get_history_metrics_handler() -> GetHistoryMetricsHandler:
    return GetHistoryMetricsHandler(_job_repository())


def get_history_metrics_handler() -> GetHistoryMetricsHandler:
    """Provide a cached history metrics handler."""
    return _get_history_metrics_handler()


@lru_cache()
def _get_low_confidence_fields_handler() -> ListLowConfidenceFieldsHandler:
    return ListLowConfidenceFieldsHandler(_job_repository(), _confidence_calculator())


def get_low_confidence_fields_handler() -> ListLowConfidenceFieldsHandler:
    """Provide a cached low-confidence fields handler."""
    return _get_low_confidence_fields_handler()


@lru_cache()
def _get_aggregated_results_handler() -> GetAggregatedResultsHandler:
    return GetAggregatedResultsHandler(_job_repository())


def get_aggregated_results_handler() -> GetAggregatedResultsHandler:
    """Provide a cached aggregated results handler."""
    return _get_aggregated_results_handler()


@lru_cache()
def _mapping_client() -> AzureMappingClient:
    return AzureMappingClient()


@lru_cache()
def _get_canonical_bundle_handler() -> GetCanonicalBundleHandler:
    return GetCanonicalBundleHandler(
        _job_repository(),
        _mapping_client(),
        history_loader=get_job,
    )


def get_canonical_bundle_handler() -> GetCanonicalBundleHandler:
    """Provide a cached canonical bundle handler."""
    return _get_canonical_bundle_handler()


def _load_history_job(job_id: str):
    job = job_store.get(job_id)
    if job:
        return job
    snapshot_job = load_job_from_snapshot(job_id)
    if snapshot_job:
        job_store.add(snapshot_job)
        return snapshot_job
    return None


@lru_cache()
def _get_history_job_detail_handler() -> GetHistoryJobDetailHandler:
    return GetHistoryJobDetailHandler(_load_history_job)


def get_history_job_detail_handler() -> GetHistoryJobDetailHandler:
    """Provide a cached history job detail handler."""
    return _get_history_job_detail_handler()


@lru_cache()
def _get_upload_document_handler() -> UploadDocumentHandler:
    return UploadDocumentHandler(create_job, create_markdown_job)


def get_upload_document_handler() -> UploadDocumentHandler:
    """Provide a cached upload document handler."""
    return _get_upload_document_handler()


def get_job_starter() -> Callable:
    """Expose job processing starter callable."""
    return start_job_processing
