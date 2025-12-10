"""File-based implementation of PageRepository using Job aggregates."""

import logging
from typing import List, Optional

from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.repositories.page_repository import PageRepository
from backend.domain.exceptions import RepositoryError

logger = logging.getLogger(__name__)


class FilePageRepository(PageRepository):
    """Persist pages by mutating Job aggregates backed by File storage."""

    def __init__(self, job_repository: JobRepository):
        self.job_repository = job_repository

    def save_page(self, job_id: str, page: PageExtraction) -> None:
        job = self.job_repository.find_by_id(job_id)
        if job is None:
            raise RepositoryError(f"Job {job_id} not found, cannot save page")

        updated_job = job.update_page(page.page_number, page)
        self.job_repository.save(updated_job)

    def find_page(self, job_id: str, page_number: int) -> Optional[PageExtraction]:
        job = self.job_repository.find_by_id(job_id)
        if job is None:
            return None
        return job.get_page(page_number)

    def find_all_pages(self, job_id: str) -> List[PageExtraction]:
        job = self.job_repository.find_by_id(job_id)
        if job is None:
            return []
        return sorted(job.pages, key=lambda page: page.page_number)

    def delete_page(self, job_id: str, page_number: int) -> bool:
        job = self.job_repository.find_by_id(job_id)
        if job is None:
            return False

        if job.get_page(page_number) is None:
            return False

        updated_job = job.remove_page(page_number)
        self.job_repository.save(updated_job)
        return True

    def delete_all_pages(self, job_id: str) -> int:
        job = self.job_repository.find_by_id(job_id)
        if job is None:
            return 0

        count = len(job.pages)
        if count == 0:
            return 0

        updated_job = job.clear_pages()
        self.job_repository.save(updated_job)
        return count

    def page_exists(self, job_id: str, page_number: int) -> bool:
        return self.find_page(job_id, page_number) is not None

    def count_pages(self, job_id: str) -> int:
        job = self.job_repository.find_by_id(job_id)
        if job is None:
            return 0
        return len(job.pages)
