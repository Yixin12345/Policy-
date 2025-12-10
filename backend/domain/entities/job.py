"""
Job Entity - Represents a document processing job.

The Job entity is the aggregate root for the document processing domain.
It contains metadata about the job and aggregates PageExtraction entities.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional

from backend.domain.value_objects.job_status import JobStatus
from backend.domain.entities.page_extraction import PageExtraction


@dataclass(frozen=True)
class Job:
    """
    Job aggregate root.
    
    Represents a document processing job with its status, pages, and metadata.
    This is an immutable entity - use factory methods to create modified versions.
    """
    
    job_id: str
    filename: str
    status: JobStatus
    total_pages: Optional[int]
    pages: List[PageExtraction] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    source_path: Optional[str] = None
    
    def with_status(self, status: JobStatus) -> "Job":
        """Create a new Job with updated status."""
        return Job(
            job_id=self.job_id,
            filename=self.filename,
            status=status,
            total_pages=self.total_pages,
            pages=list(self.pages),
            created_at=self.created_at,
            updated_at=datetime.now(),
            source_path=self.source_path,
        )
    
    def add_page(self, page: PageExtraction) -> "Job":
        """Create a new Job with an additional page."""
        new_pages = list(self.pages)
        new_pages.append(page)
        return self.with_pages(new_pages)
    
    def update_page(self, page_number: int, page: PageExtraction) -> "Job":
        """Create a new Job with an updated page."""
        new_pages = []
        replaced = False
        for existing in self.pages:
            if existing.page_number == page_number:
                new_pages.append(page)
                replaced = True
            else:
                new_pages.append(existing)
        if not replaced:
            new_pages.append(page)
        return self.with_pages(new_pages)

    def with_pages(self, pages: Iterable[PageExtraction]) -> "Job":
        """Create a new Job with the supplied pages."""
        return Job(
            job_id=self.job_id,
            filename=self.filename,
            status=self.status,
            total_pages=self.total_pages,
            pages=list(pages),
            created_at=self.created_at,
            updated_at=datetime.now(),
            source_path=self.source_path,
        )

    def with_total_pages(self, total_pages: Optional[int]) -> "Job":
        """Return job with updated total page count."""
        return Job(
            job_id=self.job_id,
            filename=self.filename,
            status=self.status,
            total_pages=total_pages,
            pages=list(self.pages),
            created_at=self.created_at,
            updated_at=datetime.now(),
            source_path=self.source_path,
        )

    def with_source_path(self, source_path: Optional[str]) -> "Job":
        """Return job with updated source path metadata."""
        return Job(
            job_id=self.job_id,
            filename=self.filename,
            status=self.status,
            total_pages=self.total_pages,
            pages=list(self.pages),
            created_at=self.created_at,
            updated_at=datetime.now(),
            source_path=source_path,
        )

    def get_page(self, page_number: int) -> Optional[PageExtraction]:
        """Get page by page number."""
        for page in self.pages:
            if page.page_number == page_number:
                return page
        return None

    def remove_page(self, page_number: int) -> "Job":
        """Return job without the specified page."""
        filtered = [page for page in self.pages if page.page_number != page_number]
        return self.with_pages(filtered)

    def clear_pages(self) -> "Job":
        """Return job with no pages."""
        return self.with_pages([])
    
    def is_complete(self) -> bool:
        """Check if job is complete."""
        return self.status.is_successful()
    
    def is_in_progress(self) -> bool:
        """Check if job is currently being processed."""
        return self.status.is_active()
    
    def has_errors(self) -> bool:
        """Check if job has errors."""
        return self.status.is_failed()

    def mark_processing(self, progress: float = 0.0) -> "Job":
        """Return job marked as running."""
        return self.with_status(JobStatus.running(progress=progress))

    def mark_completed(self) -> "Job":
        """Return job marked as completed."""
        return self.with_status(JobStatus.completed())

    def mark_partial(self, progress: float) -> "Job":
        """Return job marked as partial with given progress."""
        return self.with_status(JobStatus.partial(progress=progress))

    def mark_failed(self, message: str) -> "Job":
        """Return job marked as failed with error message."""
        return self.with_status(JobStatus.error(message))

    def mark_cancelled(self) -> "Job":
        """Return job marked as cancelled."""
        return self.with_status(JobStatus.cancelled())
    
    @classmethod
    def create(
        cls,
        job_id: str,
        filename: str,
        total_pages: Optional[int] = None,
        source_path: Optional[str] = None,
    ) -> "Job":
        """Create a new job in queued status."""
        return cls(
            job_id=job_id,
            filename=filename,
            status=JobStatus.queued(),
            total_pages=total_pages,
            pages=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            source_path=source_path,
        )
