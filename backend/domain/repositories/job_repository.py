"""Job repository interface (Abstract Base Class)."""

from abc import ABC, abstractmethod
from typing import List, Optional

from backend.domain.entities.job import Job


class JobRepository(ABC):
    """Abstract repository for Job aggregates."""

    @abstractmethod
    def save(self, job: Job) -> None:
        """Persist the given job aggregate."""

    @abstractmethod
    def find_by_id(self, job_id: str) -> Optional[Job]:
        """Return the job with the provided identifier, if it exists."""

    @abstractmethod
    def find_all(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> List[Job]:
        """Return jobs with optional pagination and sorting by created_at."""

    @abstractmethod
    def find_by_status(
        self,
        status: str,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> List[Job]:
        """Return jobs filtered by status with optional pagination."""

    @abstractmethod
    def delete(self, job_id: str) -> bool:
        """Delete the job and associated data; return True if removed."""

    @abstractmethod
    def exists(self, job_id: str) -> bool:
        """Return True when a snapshot for the job exists."""

    @abstractmethod
    def count(self, status: Optional[str] = None) -> int:
        """Return total number of jobs, optionally filtered by status."""
