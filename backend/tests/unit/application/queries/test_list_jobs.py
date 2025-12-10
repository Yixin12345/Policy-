"""
Unit tests for ListJobs query handler.

Tests the query handler with a mocked repository to ensure:
- Pagination works correctly
- Filtering by status works
- Sorting works
- DTO mapping is correct
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from backend.application.queries.list_jobs import (
    ListJobsQuery,
    ListJobsHandler,
    SortOrder,
)
from backend.application.dto.job_dto import JobsListDTO
from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus


class TestListJobsHandler:
    """Test cases for ListJobsHandler."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create a mock job repository."""
        return Mock()
    
    @pytest.fixture
    def handler(self, mock_repository):
        """Create handler with mocked repository."""
        return ListJobsHandler(mock_repository)
    
    @pytest.fixture
    def sample_jobs(self):
        """Create sample jobs for testing."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)
        return [
            Job(
                job_id="job-1",
                filename="doc1.pdf",
                status=JobStatus.completed(),
                total_pages=5,
                pages=[],
                created_at=base_time,
                updated_at=base_time + timedelta(hours=1),
            ),
            Job(
                job_id="job-2",
                filename="doc2.pdf",
                status=JobStatus.running(progress=0.5),
                total_pages=10,
                pages=[],
                created_at=base_time + timedelta(hours=1),
                updated_at=base_time + timedelta(hours=2),
            ),
            Job(
                job_id="job-3",
                filename="doc3.pdf",
                status=JobStatus.queued(),
                total_pages=3,
                pages=[],
                created_at=base_time + timedelta(hours=2),
                updated_at=base_time + timedelta(hours=2),
            ),
        ]
    
    def test_handle_returns_jobs_list_dto(self, handler, mock_repository, sample_jobs):
        """Test successful query returns JobsListDTO."""
        # Arrange
        query = ListJobsQuery()
        mock_repository.find_all.return_value = sample_jobs
        mock_repository.count.return_value = 3
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert isinstance(result, JobsListDTO)
        assert len(result.jobs) == 3
        assert result.total == 3
        assert result.page == 1
        assert result.page_size == 20
    
    def test_handle_maps_job_fields_correctly(self, handler, mock_repository, sample_jobs):
        """Test job data is correctly mapped to DTOs."""
        # Arrange
        query = ListJobsQuery()
        mock_repository.find_all.return_value = sample_jobs
        mock_repository.count.return_value = 3
        
        # Act
        result = handler.handle(query)
        
        # Assert - First job
        job1 = result.jobs[0]
        assert job1.job_id == "job-1"
        assert job1.filename == "doc1.pdf"
        assert job1.status == "completed"
        assert job1.progress == 1.0
        assert job1.total_pages == 5
        assert job1.created_at == datetime(2025, 1, 1, 12, 0, 0)
        
        # Assert - Second job
        job2 = result.jobs[1]
        assert job2.job_id == "job-2"
        assert job2.status == "running"
        assert job2.progress == 0.5
    
    def test_handle_with_pagination(self, handler, mock_repository, sample_jobs):
        """Test pagination parameters are passed correctly."""
        # Arrange
        query = ListJobsQuery(page=2, page_size=10)
        mock_repository.find_all.return_value = []
        mock_repository.count.return_value = 25
        
        # Act
        result = handler.handle(query)
        
        # Assert
        mock_repository.find_all.assert_called_once_with(
            limit=10,
            offset=10,  # (page-1) * page_size = (2-1) * 10 = 10
            sort_desc=True,
        )
        assert result.page == 2
        assert result.page_size == 10
        assert result.total == 25
    
    def test_handle_with_status_filter(self, handler, mock_repository):
        """Test filtering by status works."""
        # Arrange
        completed_jobs = [
            Job(
                job_id="job-1",
                filename="doc1.pdf",
                status=JobStatus.completed(),
                total_pages=5,
                pages=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]
        query = ListJobsQuery(status_filter="completed")
        mock_repository.find_by_status.return_value = completed_jobs
        mock_repository.count.return_value = 1
        
        # Act
        result = handler.handle(query)
        
        # Assert
        mock_repository.find_by_status.assert_called_once()
        mock_repository.count.assert_called_once_with(status="completed")
        assert len(result.jobs) == 1
        assert result.jobs[0].status == "completed"
    
    def test_handle_with_status_filter_pagination(self, handler, mock_repository):
        """Test pagination works with status filter."""
        # Arrange
        query = ListJobsQuery(page=2, page_size=5, status_filter="running")
        mock_repository.find_by_status.return_value = []
        mock_repository.count.return_value = 0
        
        # Act
        handler.handle(query)
        
        # Assert - Should call with correct offset
        mock_repository.find_by_status.assert_called_once_with(
            status="running",
            limit=5,
            offset=5,
            sort_desc=True,
        )
        mock_repository.count.assert_called_once_with(status="running")
    
    def test_handle_with_sort_ascending(self, handler, mock_repository):
        """Test ascending sort order."""
        # Arrange
        query = ListJobsQuery(sort_order=SortOrder.ASC)
        mock_repository.find_all.return_value = []
        mock_repository.count.return_value = 0
        
        # Act
        handler.handle(query)
        
        # Assert
        mock_repository.find_all.assert_called_once_with(
            limit=20,
            offset=0,
            sort_desc=False,  # ASC = sort_desc=False
        )
    
    def test_handle_with_sort_descending(self, handler, mock_repository):
        """Test descending sort order (default)."""
        # Arrange
        query = ListJobsQuery(sort_order=SortOrder.DESC)
        mock_repository.find_all.return_value = []
        mock_repository.count.return_value = 0
        
        # Act
        handler.handle(query)
        
        # Assert
        mock_repository.find_all.assert_called_once_with(
            limit=20,
            offset=0,
            sort_desc=True,  # DESC = sort_desc=True
        )
    
    def test_handle_with_empty_results(self, handler, mock_repository):
        """Test handling when no jobs exist."""
        # Arrange
        query = ListJobsQuery()
        mock_repository.find_all.return_value = []
        mock_repository.count.return_value = 0
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert len(result.jobs) == 0
        assert result.total == 0
        assert result.page == 1
        assert result.page_size == 20
    
    def test_handle_default_pagination(self, handler, mock_repository):
        """Test default pagination values."""
        # Arrange
        query = ListJobsQuery()  # Default page=1, page_size=20
        mock_repository.find_all.return_value = []
        mock_repository.count.return_value = 0
        
        # Act
        handler.handle(query)
        
        # Assert
        mock_repository.find_all.assert_called_once_with(
            limit=20,
            offset=0,
            sort_desc=True,
        )
    
    def test_handle_calculates_offset_correctly(self, handler, mock_repository):
        """Test offset calculation for various pages."""
        # Arrange
        mock_repository.find_all.return_value = []
        mock_repository.count.return_value = 0
        
        # Test page 1
        handler.handle(ListJobsQuery(page=1, page_size=10))
        assert mock_repository.find_all.call_args[1]["offset"] == 0
        
        # Test page 3
        handler.handle(ListJobsQuery(page=3, page_size=10))
        assert mock_repository.find_all.call_args[1]["offset"] == 20
        
        # Test page 5 with different page size
        handler.handle(ListJobsQuery(page=5, page_size=25))
        assert mock_repository.find_all.call_args[1]["offset"] == 100
    
    def test_query_is_immutable(self):
        """Test query object is immutable."""
        query = ListJobsQuery(page=1)
        
        with pytest.raises(AttributeError):
            query.page = 2  # type: ignore
    
    def test_sort_order_enum(self):
        """Test SortOrder enum values."""
        assert SortOrder.ASC.value == "asc"
        assert SortOrder.DESC.value == "desc"
