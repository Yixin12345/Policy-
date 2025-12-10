"""Page repository interface (Abstract Base Class)."""

from abc import ABC, abstractmethod
from typing import List, Optional

from backend.domain.entities.page_extraction import PageExtraction


class PageRepository(ABC):
    """Abstract repository responsible for persisting page extractions."""

    @abstractmethod
    def save_page(self, job_id: str, page: PageExtraction) -> None:
        """Persist the supplied page for the given job."""

    @abstractmethod
    def find_page(self, job_id: str, page_number: int) -> Optional[PageExtraction]:
        """Return the requested page extraction if it exists."""

    @abstractmethod
    def find_all_pages(self, job_id: str) -> List[PageExtraction]:
        """Return all page extractions for a job ordered by page number."""

    @abstractmethod
    def delete_page(self, job_id: str, page_number: int) -> bool:
        """Delete a specific page; return True if removed."""

    @abstractmethod
    def delete_all_pages(self, job_id: str) -> int:
        """Remove every page for the job; return number deleted."""

    @abstractmethod
    def page_exists(self, job_id: str, page_number: int) -> bool:
        """Return True when the page snapshot exists."""

    @abstractmethod
    def count_pages(self, job_id: str) -> int:
        """Return number of pages currently stored for the job."""
