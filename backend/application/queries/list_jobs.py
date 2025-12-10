"""
ListJobs Query - Retrieves paginated list of jobs with filtering and sorting.

This query supports:
- Pagination (page, page_size)
- Filtering by status
- Sorting by created_at (descending)
"""
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

from backend.domain.repositories.job_repository import JobRepository
from backend.application.dto.job_dto import JobsListDTO, JobListItemDTO


class SortOrder(Enum):
    """Sort order options."""
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True)
class ListJobsQuery:
    """Query to list jobs with pagination and filtering."""
    
    page: int = 1
    page_size: int = 20
    status_filter: Optional[str] = None
    sort_order: SortOrder = SortOrder.DESC


class ListJobsHandler:
    """Handles ListJobs queries."""
    
    def __init__(self, job_repository: JobRepository):
        """
        Initialize handler with repository dependency.
        
        Args:
            job_repository: Repository for accessing job data
        """
        self._job_repository = job_repository
    
    def handle(self, query: ListJobsQuery) -> JobsListDTO:
        """
        Execute the query and return paginated job list.
        
        Args:
            query: The ListJobs query
            
        Returns:
            JobsListDTO with paginated job list
        """
        # Get filtered jobs
        if query.status_filter:
            jobs = self._job_repository.find_by_status(
                status=query.status_filter,
                limit=query.page_size,
                offset=(query.page - 1) * query.page_size,
                sort_desc=(query.sort_order == SortOrder.DESC),
            )
            total = self._job_repository.count(status=query.status_filter)
        else:
            jobs = self._job_repository.find_all(
                limit=query.page_size,
                offset=(query.page - 1) * query.page_size,
                sort_desc=(query.sort_order == SortOrder.DESC),
            )
            total = self._job_repository.count()
        
        # Convert to DTOs
        job_dtos: List[JobListItemDTO] = []
        for job in jobs:
            job_dtos.append(JobListItemDTO(
                job_id=job.job_id,
                status=job.status.state.value,
                filename=job.filename,
                created_at=job.created_at,
                progress=job.status.progress,
                total_pages=job.total_pages,
            ))
        
        return JobsListDTO(
            jobs=job_dtos,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )
