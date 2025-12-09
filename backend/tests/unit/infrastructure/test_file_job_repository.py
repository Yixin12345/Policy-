"""Unit tests for FileJobRepository using domain aggregates."""

import json
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.entities.table_extraction import TableExtraction
from backend.domain.services.canonical_mapper import CanonicalMapper
from backend.domain.value_objects.job_status import JobStatus, JobState
from backend.infrastructure.persistence.file_job_repository import FileJobRepository
from backend.domain.exceptions import RepositoryError


def make_job(
    job_id: str,
    filename: str,
    status: JobStatus,
    created_at: datetime,
    total_pages: int = 1,
    source_path: str | None = None,
) -> Job:
    pages = [PageExtraction.create(page_number=i + 1) for i in range(total_pages)]
    return Job(
        job_id=job_id,
        filename=filename,
        status=status,
        total_pages=total_pages,
        pages=pages,
        created_at=created_at,
        updated_at=created_at,
        source_path=source_path,
    )


class TestFileJobRepository:
    """Test suite for the aggregate-based FileJobRepository."""

    @pytest.fixture
    def temp_dir(self):
        temp_path = Path(tempfile.mkdtemp())
        yield str(temp_path)
        if temp_path.exists():
            shutil.rmtree(temp_path)

    @pytest.fixture
    def repository(self, temp_dir):
        return FileJobRepository(base_dir=temp_dir)

    def test_save_and_find_by_id_roundtrip(self, repository):
        job = make_job(
            job_id="job-123",
            filename="document.pdf",
            status=JobStatus.completed(),
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            total_pages=2,
            source_path="/data/document.pdf",
        )

        repository.save(job)

        loaded = repository.find_by_id("job-123")
        assert loaded is not None
        assert loaded.job_id == job.job_id
        assert loaded.filename == "document.pdf"
        assert loaded.status.state is JobState.COMPLETED
        assert len(loaded.pages) == 2
        assert loaded.source_path == "/data/document.pdf"

    def test_save_persists_snapshot_file(self, repository, temp_dir):
        job = make_job(
            job_id="job-save",
            filename="save.pdf",
            status=JobStatus.queued(),
            created_at=datetime.now(timezone.utc),
        )

        repository.save(job)

        snapshot_path = Path(temp_dir) / "job-save" / "job_snapshot.json"
        assert snapshot_path.exists()
        payload = json.loads(snapshot_path.read_text())
        assert payload["filename"] == "save.pdf"
        assert payload["status"] == JobState.QUEUED.value

    def test_save_overwrites_existing_job(self, repository):
        job = make_job(
            job_id="job-edit",
            filename="initial.pdf",
            status=JobStatus.queued(),
            created_at=datetime.now(timezone.utc),
        )
        repository.save(job)

        updated_job = job.mark_failed("boom")
        repository.save(updated_job)

        loaded = repository.find_by_id("job-edit")
        assert loaded is not None
        assert loaded.status.state is JobState.ERROR
        assert loaded.status.error_message == "boom"

    def test_find_by_id_returns_none_when_missing(self, repository):
        assert repository.find_by_id("unknown") is None

    def test_exists_matches_snapshot_presence(self, repository):
        job = make_job(
            job_id="job-exists",
            filename="exists.pdf",
            status=JobStatus.running(0.2),
            created_at=datetime.now(timezone.utc),
        )
        repository.save(job)

        assert repository.exists("job-exists") is True
        assert repository.exists("other") is False

    def test_delete_removes_snapshot(self, repository, temp_dir):
        job = make_job(
            job_id="job-delete",
            filename="delete.pdf",
            status=JobStatus.queued(),
            created_at=datetime.now(timezone.utc),
        )
        repository.save(job)

        assert repository.delete("job-delete") is True
        assert not (Path(temp_dir) / "job-delete").exists()

    def test_delete_returns_false_when_missing(self, repository):
        assert repository.delete("unknown") is False

    def test_count_supports_status_filter(self, repository):
        base_time = datetime(2024, 1, 1)
        repository.save(make_job("job-a", "a.pdf", JobStatus.completed(), base_time))
        repository.save(make_job("job-b", "b.pdf", JobStatus.running(0.5), base_time + timedelta(minutes=1)))

        assert repository.count() == 2
        assert repository.count(status="completed") == 1
        assert repository.count(status="running") == 1

    def test_find_all_orders_by_created_at_desc(self, repository):
        base_time = datetime(2024, 1, 1)
        repository.save(make_job("job1", "one.pdf", JobStatus.queued(), base_time))
        repository.save(make_job("job2", "two.pdf", JobStatus.queued(), base_time + timedelta(hours=1)))
        repository.save(make_job("job3", "three.pdf", JobStatus.queued(), base_time + timedelta(hours=2)))

        jobs = repository.find_all()
        ids = [job.job_id for job in jobs]
        assert ids == ["job3", "job2", "job1"]

    def test_find_all_respects_pagination(self, repository):
        base_time = datetime(2024, 1, 1)
        for index in range(5):
            repository.save(
                make_job(
                    job_id=f"job-{index}",
                    filename=f"file-{index}.pdf",
                    status=JobStatus.queued(),
                    created_at=base_time + timedelta(minutes=index),
                )
            )

        page = repository.find_all(limit=2, offset=1)
        assert len(page) == 2
        # Offset=1 means we skip newest (job-4)
        assert [job.job_id for job in page] == ["job-3", "job-2"]

    def test_find_by_status_filters_and_orders(self, repository):
        base_time = datetime(2024, 1, 1)
        repository.save(make_job("done-1", "done1.pdf", JobStatus.completed(), base_time))
        repository.save(make_job("running-1", "run.pdf", JobStatus.running(0.3), base_time + timedelta(minutes=1)))
        repository.save(make_job("done-2", "done2.pdf", JobStatus.completed(), base_time + timedelta(minutes=2)))

        completed = repository.find_by_status("completed")
        assert [job.job_id for job in completed] == ["done-2", "done-1"]

        paged = repository.find_by_status("completed", limit=1, offset=1)
        assert len(paged) == 1
        assert paged[0].job_id == "done-1"

    def test_save_and_load_preserves_pages(self, repository):
        job = make_job(
            job_id="job-pages",
            filename="pages.pdf",
            status=JobStatus.running(0.1),
            created_at=datetime.now(timezone.utc),
            total_pages=3,
        )
        repository.save(job)

        loaded = repository.find_by_id("job-pages")
        assert loaded is not None
        assert len(loaded.pages) == 3
        assert [page.page_number for page in loaded.pages] == [1, 2, 3]

    def test_find_by_id_raises_on_corrupted_snapshot(self, repository, temp_dir):
        job_dir = Path(temp_dir) / "corrupt"
        job_dir.mkdir(parents=True)
        (job_dir / "job_snapshot.json").write_text("{not valid json", encoding="utf-8")

        with pytest.raises(RepositoryError):
            repository.find_by_id("corrupt")

    def test_snapshot_contains_expected_structure(self, repository, temp_dir):
        job = make_job(
            job_id="job-structure",
            filename="structure.pdf",
            status=JobStatus.queued(),
            created_at=datetime(2024, 1, 1),
        )
        repository.save(job)

        snapshot_path = Path(temp_dir) / "job-structure" / "job_snapshot.json"
        data = json.loads(snapshot_path.read_text())
        assert set(data.keys()) >= {"job_id", "filename", "status", "pages", "created_at"}
        assert isinstance(data["pages"], list)

    def test_normalize_table_dict_preserves_headers_and_rows(self, repository):
        raw_table = {
            "id": "charges_table",
            "page": 1,
            "confidence": 0.82,
            "columns": [
                {"key": "rev_code", "header": "Rev Code"},
                {"key": "description", "header": "Description"},
                {"key": "rate", "header": "HCPCS/Rate"},
                {"key": "service_date", "header": "Service Date"},
                {"key": "units", "header": "Units"},
                {"key": "total", "header": "Total Charges"},
            ],
            "rows": [
                ["0022", "Room and Board", "", "", "1", "0.00"],
                ["0120", "Standard Level of Care", "733.00", "022825", "1", "733.00"],
            ],
        }

        normalized = repository._normalize_table_dict(raw_table)
        table = TableExtraction.from_dict(normalized)

        header_cells = table.get_headers()
        assert [cell.content for cell in header_cells] == [
            "Rev Code",
            "Description",
            "HCPCS/Rate",
            "Service Date",
            "Units",
            "Total Charges",
        ]

        mapper = CanonicalMapper()
        extracted = mapper._extract_line_items(table, page_number=1)

        assert extracted is not None
        assert extracted["confidence"] == pytest.approx(0.82, abs=1e-6)
        first_item = extracted["items"][0]
        assert first_item["revenueCode"]["value"] == "0022"
        assert first_item["description"]["value"] == "Room and Board"

