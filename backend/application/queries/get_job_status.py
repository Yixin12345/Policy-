"""
GetJobStatus Query - Retrieves current status of a processing job.

This query follows the CQRS pattern and uses the repository pattern
to fetch job status without modifying state.
"""
from dataclasses import dataclass
from typing import Optional

from backend.application.dto.job_dto import JobStatusDTO
from backend.domain.exceptions import EntityNotFoundError
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.value_objects.job_status import JobState


@dataclass(frozen=True)
class GetJobStatusQuery:
    """Query to get status of a specific job."""
    
    job_id: str


class GetJobStatusHandler:
    """Handles GetJobStatus queries."""
    
    def __init__(self, job_repository: JobRepository):
        """
        Initialize handler with repository dependency.
        
        Args:
            job_repository: Repository for accessing job data
        """
        self._job_repository = job_repository
    
    def handle(self, query: GetJobStatusQuery) -> JobStatusDTO:
        """
        Execute the query and return job status.
        
        Args:
            query: The GetJobStatus query
            
        Returns:
            JobStatusDTO with current job status
            
        Raises:
            EntityNotFoundError: If job not found
        """
        # Find job using repository
        job = self._job_repository.find_by_id(query.job_id)
        
        if job is None:
            raise EntityNotFoundError("Job", query.job_id, message=f"Job with ID '{query.job_id}' not found")
        
        # Convert data dict or entity to DTO
        from datetime import datetime
        
        # Handle both Job entity and dict format
        if hasattr(job, 'job_id'):
            # Job entity format
            pages = getattr(job, "pages", None)
            total_pages = job.total_pages if job.total_pages is not None else len(pages or [])
            if total_pages is None:
                total_pages = 0

            page_count = len(pages or [])
            bounded_page_count = min(page_count, total_pages) if total_pages else page_count

            progress_estimate = 0
            if total_pages:
                progress_estimate = int(round(job.status.progress * total_pages))
                progress_estimate = max(0, min(progress_estimate, total_pages))

            inferred_processed = 0
            if pages:
                inferred_processed = sum(
                    1
                    for page in pages
                    if (
                        getattr(page, "fields", None)
                        and len(getattr(page, "fields", ())) > 0
                    )
                    or (
                        getattr(page, "tables", None)
                        and len(getattr(page, "tables", ())) > 0
                    )
                )
                if total_pages:
                    inferred_processed = min(inferred_processed, total_pages)

            if job.status.state in {JobState.QUEUED, JobState.RUNNING}:
                processed_pages = max(progress_estimate, inferred_processed)
            else:
                processed_pages = max(progress_estimate, bounded_page_count)
                if processed_pages == 0 and bounded_page_count:
                    processed_pages = bounded_page_count

            if total_pages:
                processed_pages = min(processed_pages, total_pages)

            return JobStatusDTO(
                job_id=job.job_id,
                status=job.status.state.value,
                progress=job.status.progress,
                filename=job.filename,
                created_at=job.created_at,
                updated_at=job.updated_at,
                error_message=job.status.error_message,
                total_pages=total_pages,
                processed_pages=processed_pages,
            )
        else:
            # Dict format from FileJobRepository
            # Parse datetime strings if needed
            created_at = job.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

            updated_at = job.get("updated_at")
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

            total_pages = job.get("page_count") or job.get("total_pages") or 0
            pages_snapshot = job.get("pages", []) or []
            page_count = len(pages_snapshot)
            bounded_page_count = min(page_count, total_pages) if total_pages else page_count

            raw_progress = job.get("progress", 0.0)
            try:
                progress_value = float(raw_progress)
            except (TypeError, ValueError):
                progress_value = 0.0
            if progress_value > 1:
                progress_value = progress_value / 100.0
            progress_value = max(0.0, min(progress_value, 1.0))

            progress_estimate = 0
            if total_pages:
                progress_estimate = int(round(progress_value * total_pages))
                progress_estimate = max(0, min(progress_estimate, total_pages))

            inferred_processed = 0
            if pages_snapshot:
                inferred_processed = sum(
                    1
                    for entry in pages_snapshot
                    if isinstance(entry, dict)
                    and (
                        (entry.get("fields") and len(entry.get("fields", [])) > 0)
                        or (entry.get("tables") and len(entry.get("tables", [])) > 0)
                    )
                )
                if total_pages:
                    inferred_processed = min(inferred_processed, total_pages)

            status_entry = job.get("status")
            state_str = None
            if isinstance(status_entry, dict):
                state_str = status_entry.get("state") or status_entry.get("status")
            elif isinstance(status_entry, str):
                state_str = status_entry

            job_state = None
            if isinstance(state_str, str):
                try:
                    job_state = JobState(state_str.lower())
                except ValueError:
                    job_state = None

            if job_state in {JobState.QUEUED, JobState.RUNNING}:
                processed_pages = max(progress_estimate, inferred_processed)
            else:
                processed_pages = max(progress_estimate, bounded_page_count)
                if processed_pages == 0 and bounded_page_count:
                    processed_pages = bounded_page_count

            if total_pages:
                processed_pages = min(processed_pages, total_pages)

            return JobStatusDTO(
                job_id=job.get("job_id"),
                status=state_str or job.get("status"),
                progress=progress_value,
                filename=job.get("metadata", {}).get("filename") or job.get("filename", ""),
                created_at=created_at,
                updated_at=updated_at,
                error_message=job.get("error_message"),
                total_pages=total_pages or None,
                processed_pages=processed_pages,
            )
