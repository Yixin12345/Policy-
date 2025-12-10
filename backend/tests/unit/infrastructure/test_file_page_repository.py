"""Unit tests for FilePageRepository working with domain entities."""

import pytest
import tempfile
import shutil
from pathlib import Path

from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.exceptions import RepositoryError
from backend.infrastructure.persistence.file_job_repository import FileJobRepository
from backend.infrastructure.persistence.file_page_repository import FilePageRepository


def make_job(job_id: str, filename: str) -> Job:
    return Job.create(job_id=job_id, filename=filename)


class TestFilePageRepository:
    """Test suite verifying page persistence via job aggregates."""

    @pytest.fixture
    def temp_dir(self):
        temp_path = Path(tempfile.mkdtemp())
        yield str(temp_path)
        if temp_path.exists():
            shutil.rmtree(temp_path)

    @pytest.fixture
    def job_repository(self, temp_dir):
        return FileJobRepository(base_dir=temp_dir)

    @pytest.fixture
    def repository(self, job_repository):
        return FilePageRepository(job_repository=job_repository)

    @pytest.fixture
    def job_id(self, job_repository) -> str:
        job = make_job("job-pages", "doc.pdf")
        job_repository.save(job)
        return job.job_id

    def test_save_page_adds_new_page(self, repository, job_repository, job_id):
        page = PageExtraction.create(page_number=1)

        repository.save_page(job_id, page)

        loaded_job = job_repository.find_by_id(job_id)
        assert loaded_job is not None
        assert len(loaded_job.pages) == 1
        assert loaded_job.pages[0].page_number == 1

    def test_save_page_raises_when_job_missing(self, repository):
        with pytest.raises(RepositoryError):
            repository.save_page("missing", PageExtraction.create(page_number=1))

    def test_save_page_updates_existing_entry(self, repository, job_repository, job_id):
        original = PageExtraction.create(page_number=1)
        repository.save_page(job_id, original)

        updated = original.mark_reviewed()
        repository.save_page(job_id, updated)

        job = job_repository.find_by_id(job_id)
        assert job is not None
        page = job.get_page(1)
        assert page is not None
        assert page.has_edits is True

    def test_find_page_returns_domain_entity(self, repository, job_id):
        repository.save_page(job_id, PageExtraction.create(page_number=2))

        page = repository.find_page(job_id, 2)
        assert isinstance(page, PageExtraction)
        assert page.page_number == 2

    def test_find_all_pages_returns_sorted_pages(self, repository, job_id):
        repository.save_page(job_id, PageExtraction.create(page_number=3))
        repository.save_page(job_id, PageExtraction.create(page_number=1))
        repository.save_page(job_id, PageExtraction.create(page_number=2))

        pages = repository.find_all_pages(job_id)
        assert [page.page_number for page in pages] == [1, 2, 3]

    def test_find_page_returns_none_when_missing(self, repository, job_id):
        assert repository.find_page(job_id, 7) is None

    def test_find_page_returns_none_when_job_missing(self, repository):
        assert repository.find_page("missing", 1) is None

    def test_delete_page_removes_only_target(self, repository, job_repository, job_id):
        repository.save_page(job_id, PageExtraction.create(page_number=1))
        repository.save_page(job_id, PageExtraction.create(page_number=2))

        assert repository.delete_page(job_id, 1) is True
        assert repository.find_page(job_id, 1) is None
        assert repository.find_page(job_id, 2) is not None

    def test_delete_page_returns_false_for_missing_page(self, repository, job_id):
        assert repository.delete_page(job_id, 99) is False

    def test_delete_page_returns_false_when_job_missing(self, repository):
        assert repository.delete_page("missing", 1) is False

    def test_delete_all_pages_returns_count(self, repository, job_id):
        repository.save_page(job_id, PageExtraction.create(page_number=1))
        repository.save_page(job_id, PageExtraction.create(page_number=2))

        deleted = repository.delete_all_pages(job_id)
        assert deleted == 2
        assert repository.count_pages(job_id) == 0

    def test_delete_all_pages_returns_zero_for_missing_job(self, repository):
        assert repository.delete_all_pages("missing") == 0

    def test_page_exists_reflects_state(self, repository, job_id):
        repository.save_page(job_id, PageExtraction.create(page_number=1))
        assert repository.page_exists(job_id, 1) is True
        assert repository.page_exists(job_id, 2) is False

    def test_count_pages_tracks_totals(self, repository, job_id):
        assert repository.count_pages(job_id) == 0
        repository.save_page(job_id, PageExtraction.create(page_number=1))
        repository.save_page(job_id, PageExtraction.create(page_number=2))
        assert repository.count_pages(job_id) == 2
        repository.delete_page(job_id, 1)
        assert repository.count_pages(job_id) == 1

