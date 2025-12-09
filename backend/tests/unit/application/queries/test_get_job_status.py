"""
Unit tests for GetJobStatus query handler.

Tests the query handler with a mocked repository to ensure:
- Successful job retrieval
- Proper DTO mapping
- Error handling for not found jobs
"""
import pytest
from datetime import datetime
from unittest.mock import Mock

from backend.application.queries.get_job_status import (
    GetJobStatusQuery,
    GetJobStatusHandler,
)
from backend.application.dto.job_dto import JobStatusDTO
from backend.domain.exceptions import EntityNotFoundError
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.entities.job import Job


class TestGetJobStatusHandler:
    """Test cases for GetJobStatusHandler."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create a mock job repository."""
        return Mock()
    
    @pytest.fixture
    def handler(self, mock_repository):
        """Create handler with mocked repository."""
        return GetJobStatusHandler(mock_repository)
    
    @pytest.fixture
    def sample_job(self):
        """Create a sample job for testing."""
        return Job(
            job_id="job-123",
            filename="test.pdf",
            status=JobStatus.completed(),
            total_pages=5,
            pages=[],
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 12, 30, 0),
        )
    
    def test_handle_returns_job_status_dto(self, handler, mock_repository, sample_job):
        """Test successful query returns JobStatusDTO."""
        # Arrange
        query = GetJobStatusQuery(job_id="job-123")
        mock_repository.find_by_id.return_value = sample_job
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert isinstance(result, JobStatusDTO)
        assert result.job_id == "job-123"
        assert result.status == "completed"
        assert result.progress == 1.0
        assert result.filename == "test.pdf"
        assert result.total_pages == 5
        assert result.processed_pages == 5
        assert result.error_message is None
        mock_repository.find_by_id.assert_called_once_with("job-123")
    
    def test_handle_maps_all_job_fields(self, handler, mock_repository):
        """Test DTO contains all relevant job fields."""
        # Arrange
        job = Job(
            job_id="job-456",
            filename="invoice.pdf",
            status=JobStatus.running(progress=0.5),
            total_pages=10,
            pages=[],
            created_at=datetime(2025, 1, 2, 10, 0, 0),
            updated_at=datetime(2025, 1, 2, 10, 15, 0),
        )
        query = GetJobStatusQuery(job_id="job-456")
        mock_repository.find_by_id.return_value = job
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert result.job_id == "job-456"
        assert result.filename == "invoice.pdf"
        assert result.status == "running"
        assert result.progress == 0.5
        assert result.total_pages == 10
        assert result.created_at == datetime(2025, 1, 2, 10, 0, 0)
        assert result.updated_at == datetime(2025, 1, 2, 10, 15, 0)
    
    def test_handle_includes_error_message_when_failed(self, handler, mock_repository):
        """Test DTO includes error message for failed jobs."""
        # Arrange
        job = Job(
            job_id="job-789",
            filename="failed.pdf",
            status=JobStatus.error("Processing failed"),
            total_pages=3,
            pages=[],
            created_at=datetime(2025, 1, 3, 9, 0, 0),
            updated_at=datetime(2025, 1, 3, 9, 5, 0),
        )
        query = GetJobStatusQuery(job_id="job-789")
        mock_repository.find_by_id.return_value = job
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert result.status == "error"
        assert result.error_message == "Processing failed"
    
    def test_handle_raises_not_found_when_job_missing(self, handler, mock_repository):
        """Test raises EntityNotFoundError when job doesn't exist."""
        # Arrange
        query = GetJobStatusQuery(job_id="nonexistent")
        mock_repository.find_by_id.return_value = None
        
        # Act & Assert
        with pytest.raises(EntityNotFoundError) as exc_info:
            handler.handle(query)
        
        assert "nonexistent" in str(exc_info.value)
        mock_repository.find_by_id.assert_called_once_with("nonexistent")
    
    def test_handle_calculates_processed_pages(self, handler, mock_repository):
        """Test processed_pages equals number of pages in job."""
        # Arrange
        from backend.domain.entities.page_extraction import PageExtraction
        
        pages = [
            PageExtraction(page_number=1, fields=[], tables=[]),
            PageExtraction(page_number=2, fields=[], tables=[]),
            PageExtraction(page_number=3, fields=[], tables=[]),
        ]
        job = Job(
            job_id="job-abc",
            filename="multi.pdf",
            status=JobStatus.partial(),
            total_pages=5,
            pages=pages,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        query = GetJobStatusQuery(job_id="job-abc")
        mock_repository.find_by_id.return_value = job
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert result.total_pages == 5
        assert result.processed_pages == 3

    def test_running_job_uses_progress_over_page_count(self, handler, mock_repository):
        """Running jobs should not report all pages processed when placeholders exist."""
        from backend.domain.entities.page_extraction import PageExtraction

        pages = [
            PageExtraction.create(page_number=1),
            PageExtraction.create(page_number=2),
        ]

        job = Job(
            job_id="job-running",
            filename="processing.pdf",
            status=JobStatus.running(progress=0.0),
            total_pages=2,
            pages=pages,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        query = GetJobStatusQuery(job_id="job-running")
        mock_repository.find_by_id.return_value = job

        result = handler.handle(query)

        assert result.processed_pages == 0

    def test_running_job_counts_inferred_page_results(self, handler, mock_repository):
        """Running jobs should increment processed pages when extracts are present."""
        from backend.domain.entities.page_extraction import PageExtraction
        from backend.domain.entities.field_extraction import FieldExtraction

        field = FieldExtraction.create(field_name="invoice number", value="INV-123", confidence=0.9)

        pages = [
            PageExtraction.create(page_number=1, fields=[field]),
            PageExtraction.create(page_number=2),
        ]

        job = Job(
            job_id="job-running-progress",
            filename="processing.pdf",
            status=JobStatus.running(progress=0.0),
            total_pages=2,
            pages=pages,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        query = GetJobStatusQuery(job_id="job-running-progress")
        mock_repository.find_by_id.return_value = job

        result = handler.handle(query)

        assert result.processed_pages == 1
    
    def test_query_is_immutable(self):
        """Test query object is immutable."""
        query = GetJobStatusQuery(job_id="test")
        
        with pytest.raises(AttributeError):
            query.job_id = "changed"  # type: ignore
