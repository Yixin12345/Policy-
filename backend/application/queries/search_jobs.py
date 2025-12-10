"""
Search Jobs Query - Advanced job search with filtering and pagination

Provides flexible job search capabilities including:
- Full-text search across job names and metadata
- Status-based filtering
- Date range filtering
- Sorting by various criteria
- Pagination support

Query pattern ensures:
- Performance with proper indexing
- Type safety for all parameters
- Consistent result formatting
- Proper error handling
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from enum import Enum
import logging

from backend.domain.entities.job import Job, JobStatus
from backend.domain.exceptions import (
    DomainValidationError,
    RepositoryError
)
from backend.domain.repositories.job_repository import JobRepository


class SortField(str, Enum):
    """Available fields for sorting search results"""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at" 
    NAME = "name"
    STATUS = "status"
    PAGES_COUNT = "pages_count"
    COMPLETION_RATE = "completion_rate"


class SortDirection(str, Enum):
    """Sort direction options"""
    ASC = "asc"
    DESC = "desc"


@dataclass
class DateRange:
    """Date range filter"""
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate date range"""
        if self.start and self.end and self.start > self.end:
            raise DomainValidationError("Start date cannot be after end date")


@dataclass
class SearchJobsQuery:
    """Query to search jobs with filtering and pagination"""
    
    # Search criteria
    text_query: Optional[str] = None          # Free text search
    status_filter: Optional[List[JobStatus]] = None  # Filter by job status
    date_range: Optional[DateRange] = None    # Filter by creation/update date
    tag_filter: Optional[List[str]] = None    # Filter by tags/categories
    
    # Pagination
    page: int = 1
    page_size: int = 20
    
    # Sorting
    sort_field: SortField = SortField.CREATED_AT
    sort_direction: SortDirection = SortDirection.DESC
    
    # Result options
    include_page_count: bool = True           # Include page counts in results
    include_progress: bool = True             # Include processing progress
    include_metadata: bool = False            # Include full job metadata
    
    def __post_init__(self):
        """Validate query parameters"""
        if self.page < 1:
            raise DomainValidationError("Page number must be positive")
        
        if self.page_size < 1 or self.page_size > 100:
            raise DomainValidationError("Page size must be between 1 and 100")
        
        if self.text_query is not None and len(self.text_query.strip()) == 0:
            self.text_query = None


@dataclass
class JobSummary:
    """Summary information for a job in search results"""
    id: str
    name: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    
    # Optional fields based on query options
    page_count: Optional[int] = None
    pages_processed: Optional[int] = None
    completion_percentage: Optional[float] = None
    
    # Extended metadata if requested
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    file_info: Optional[Dict[str, Any]] = None
    processing_metadata: Optional[Dict[str, Any]] = None
    
    # Error information
    has_errors: bool = False
    error_count: int = 0


@dataclass
class SearchResult:
    """Search results with pagination information"""
    jobs: List[JobSummary]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next_page: bool
    has_previous_page: bool
    
    # Search metadata
    query_executed_at: datetime
    search_duration_ms: int


class SearchJobsHandler:
    """Handles SearchJobs query execution"""
    
    def __init__(self, job_repository: JobRepository):
        self._job_repository = job_repository
        self._logger = logging.getLogger(__name__)
    
    def handle(self, query: SearchJobsQuery) -> SearchResult:
        """
        Execute job search query
        
        Args:
            query: SearchJobsQuery with search criteria
            
        Returns:
            SearchResult with matching jobs and pagination info
            
        Raises:
            DomainValidationError: If query parameters invalid
            RepositoryError: If search execution fails
        """
        start_time = datetime.now()
        
        try:
            # 1. Build search criteria
            search_criteria = self._build_search_criteria(query)
            
            # 2. Execute search with pagination
            jobs, total_count = self._job_repository.search_jobs(
                criteria=search_criteria,
                page=query.page,
                page_size=query.page_size,
                sort_field=query.sort_field.value,
                sort_direction=query.sort_direction.value
            )
            
            # 3. Build job summaries
            job_summaries = [
                self._build_job_summary(job, query) 
                for job in jobs
            ]
            
            # 4. Calculate pagination info
            total_pages = (total_count + query.page_size - 1) // query.page_size
            
            # 5. Calculate execution time
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return SearchResult(
                jobs=job_summaries,
                total_count=total_count,
                page=query.page,
                page_size=query.page_size,
                total_pages=total_pages,
                has_next_page=query.page < total_pages,
                has_previous_page=query.page > 1,
                query_executed_at=start_time,
                search_duration_ms=duration_ms
            )
            
        except DomainValidationError:
            # Re-raise domain exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise RepositoryError(f"Failed to execute job search: {str(e)}") from e
    
    def _build_search_criteria(self, query: SearchJobsQuery) -> Dict[str, Any]:
        """Build search criteria dictionary from query"""
        criteria = {}
        
        # Text search
        if query.text_query:
            criteria['text_query'] = query.text_query.strip()
        
        # Status filter
        if query.status_filter:
            criteria['status_filter'] = [status.value for status in query.status_filter]
        
        # Date range filter
        if query.date_range:
            if query.date_range.start:
                criteria['created_after'] = query.date_range.start
            if query.date_range.end:
                criteria['created_before'] = query.date_range.end
        
        # Tag filter
        if query.tag_filter:
            criteria['tag_filter'] = query.tag_filter
        
        return criteria
    
    def _build_job_summary(self, job: Job, query: SearchJobsQuery) -> JobSummary:
        """Build JobSummary from Job entity"""
        
        summary = JobSummary(
            id=job.id,
            name=job.name,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at
        )
        
        # Add optional fields based on query options
        if query.include_page_count:
            summary.page_count = getattr(job, 'total_pages', 0)
            
        if query.include_progress:
            summary.pages_processed = getattr(job, 'pages_processed', 0)
            if summary.page_count and summary.page_count > 0:
                summary.completion_percentage = (
                    summary.pages_processed / summary.page_count * 100
                )
        
        if query.include_metadata:
            summary.description = getattr(job, 'description', None)
            summary.tags = getattr(job, 'tags', [])
            summary.file_info = getattr(job, 'file_metadata', {})
            summary.processing_metadata = getattr(job, 'processing_metadata', {})
        
        # Error information
        error_count = getattr(job, 'error_count', 0)
        summary.has_errors = error_count > 0
        summary.error_count = error_count
        
        return summary


# Convenience functions for common search patterns

def search_recent_jobs(
    job_repository: JobRepository,
    days: int = 7,
    page: int = 1,
    page_size: int = 20
) -> SearchResult:
    """Search for jobs created in the last N days"""
    from datetime import timedelta, timezone
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    query = SearchJobsQuery(
        date_range=DateRange(start=start_date, end=end_date),
        page=page,
        page_size=page_size,
        sort_field=SortField.CREATED_AT,
        sort_direction=SortDirection.DESC
    )
    
    handler = SearchJobsHandler(job_repository)
    return handler.handle(query)


def search_jobs_by_status(
    job_repository: JobRepository,
    status: JobStatus,
    page: int = 1,
    page_size: int = 20
) -> SearchResult:
    """Search for jobs with a specific status"""
    
    query = SearchJobsQuery(
        status_filter=[status],
        page=page,
        page_size=page_size,
        sort_field=SortField.UPDATED_AT,
        sort_direction=SortDirection.DESC
    )
    
    handler = SearchJobsHandler(job_repository)
    return handler.handle(query)


def search_jobs_by_text(
    job_repository: JobRepository,
    text: str,
    page: int = 1,
    page_size: int = 20
) -> SearchResult:
    """Search for jobs containing specific text"""
    
    query = SearchJobsQuery(
        text_query=text,
        page=page,
        page_size=page_size,
        sort_field=SortField.UPDATED_AT,
        sort_direction=SortDirection.DESC,
        include_metadata=True  # Include metadata for text search context
    )
    
    handler = SearchJobsHandler(job_repository)
    return handler.handle(query)