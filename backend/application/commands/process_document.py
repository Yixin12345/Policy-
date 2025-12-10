"""ProcessDocument Command - Orchestrates end-to-end document processing.

High-level orchestration only; concrete vision/pdf/mapping infrastructure
will be injected (Strategy pattern). Keeps domain logic isolated.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Dict, Any, List

from backend.domain.repositories.job_repository import JobRepository
from backend.domain.repositories.page_repository import PageRepository
from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.value_objects.job_status import JobStatus, JobState
from backend.domain.exceptions import EntityNotFoundError, EntityValidationError


class VisionClient(Protocol):
    def extract_data(self, file_path: str) -> List[Dict[str, Any]]: ...

class PdfRenderer(Protocol):
    def get_page_count(self, file_path: str) -> int: ...

class MappingClient(Protocol):
    def map(self, raw_extractions: List[Dict[str, Any]]) -> List[Dict[str, Any]]: ...


@dataclass(frozen=True)
class ProcessDocumentCommand:
    job_id: str
    file_path: str


class ProcessDocumentHandler:
    """Handles ProcessDocument commands."""

    def __init__(
        self,
        job_repository: JobRepository,
        page_repository: PageRepository,
        vision_client: VisionClient,
        pdf_renderer: PdfRenderer,
        mapping_client: MappingClient,
    ):
        self._jobs = job_repository
        self._pages = page_repository
        self._vision = vision_client
        self._pdf = pdf_renderer
        self._mapping = mapping_client

    def handle(self, command: ProcessDocumentCommand) -> Dict[str, Any]:
        # Validate job exists
        job = self._jobs.find_by_id(command.job_id)
        if job is None:
            raise EntityNotFoundError("Job", command.job_id, message=f"Job with ID '{command.job_id}' not found")
        
        # Validate job status
        if job.status.state == JobState.COMPLETED:
            raise EntityValidationError(
                "Job",
                {"status": "Job already processed"}
            )
        
        if job.status.state == JobState.RUNNING:
            raise EntityValidationError(
                "Job", 
                {"status": "Job currently being processed"}
            )
        
        file_path = Path(command.file_path)
        running_job = job.with_status(JobStatus.running(progress=0.0))

        try:
            self._jobs.save(running_job)
            self._validate_file_exists(file_path)

            raw_extractions = self._vision.extract_data(str(file_path))
            pages = self._normalize_page_extractions(raw_extractions)

            for page in pages:
                self._pages.save_page(command.job_id, page)

            # Mark job as completed
            completed_job = running_job.with_status(JobStatus.completed())
            self._jobs.save(completed_job)

            summary = self._summarize_pages(pages)
            
            return {
                "job_id": command.job_id,
                "status": "completed",
                "pages_processed": summary["pages_processed"],
                "extraction_summary": summary,
            }
        except (EntityValidationError, EntityNotFoundError) as exc:
            self._mark_job_failed(job, str(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            self._mark_job_failed(job, str(exc))
            raise  # Re-raise so tests can catch specific exceptions

    def _validate_file_exists(self, file_path: Path) -> None:
        if not file_path.exists():
            raise EntityValidationError(
                "File",
                {"path": "File not found"}
            )

    def _normalize_page_extractions(self, raw_extractions: List[Any]) -> List[PageExtraction]:
        pages: List[PageExtraction] = []
        for entry in raw_extractions:
            if isinstance(entry, PageExtraction):
                pages.append(entry)
            elif isinstance(entry, dict):
                pages.append(PageExtraction.from_dict(entry))
        return pages

    def _summarize_pages(self, pages: List[PageExtraction]) -> Dict[str, Any]:
        total_fields = sum(len(page.fields) for page in pages)
        total_tables = sum(len(page.tables) for page in pages)
        low_confidence_pages = sum(1 for page in pages if page.has_low_confidence_items())
        return {
            "pages_processed": len(pages),
            "total_fields": total_fields,
            "total_tables": total_tables,
            "low_confidence_pages": low_confidence_pages,
        }

    def _mark_job_failed(self, job: Job, reason: str) -> None:
        try:
            failed_job = job.with_status(JobStatus.error(reason))
            self._jobs.save(failed_job)
        except Exception:
            # Repository may already be failing; best-effort only
            pass
