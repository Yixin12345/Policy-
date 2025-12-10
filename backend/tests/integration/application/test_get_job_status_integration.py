"""Integration tests for GetJobStatus query handler.

These tests verify the entire flow from query → handler → repository → filesystem.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.application.queries.get_job_status import (
    GetJobStatusHandler,
    GetJobStatusQuery,
)
from backend.domain.exceptions import EntityNotFoundError
from backend.infrastructure.persistence.file_job_repository import FileJobRepository


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def job_repository(temp_data_dir):
    """Create a real FileJobRepository for integration testing."""
    return FileJobRepository(base_dir=str(temp_data_dir))


@pytest.fixture
def sample_job_data(temp_data_dir):
    """Create a sample job JSON file in the temp directory."""
    job_id = "test-job-123"
    job_dir = temp_data_dir / job_id
    job_dir.mkdir(parents=True)
    
    job_data = {
        "job_id": job_id,
        "status": "completed",
        "progress": 1.0,
        "created_at": "2025-11-19T10:00:00Z",
        "updated_at": "2025-11-19T10:05:00Z",
        "page_count": 5,
        "error_message": None,
        "metadata": {
            "filename": "test-document.pdf",
            "file_size": 1024000,
        },
        "pages": [1, 2, 3, 4, 5]  # Mock pages for length calculation
    }
    
    with open(job_dir / "job_snapshot.json", "w") as f:
        json.dump(job_data, f, indent=2)
    
    return job_data


class TestGetJobStatusIntegration:
    """Integration tests for GetJobStatus query end-to-end."""

    def test_get_job_status_end_to_end(self, job_repository, sample_job_data):
        """Test complete flow: query → handler → repository → file system."""
        # Arrange
        handler = GetJobStatusHandler(job_repository)
        query = GetJobStatusQuery(job_id="test-job-123")

        # Act
        result = handler.handle(query)

        # Assert
        assert result.job_id == "test-job-123"
        assert result.status == "completed"
        assert result.progress == 1.0
        assert result.total_pages == 5
        assert result.processed_pages == 5
        assert result.filename == "test-document.pdf"
        assert result.error_message is None

    def test_get_job_status_not_found(self, job_repository):
        """Test error handling when job doesn't exist."""
        # Arrange
        handler = GetJobStatusHandler(job_repository)
        query = GetJobStatusQuery(job_id="nonexistent-job")

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match="Job with ID 'nonexistent-job' not found"):
            handler.handle(query)

    def test_get_job_status_with_error_message(self, job_repository, temp_data_dir):
        """Test retrieving a job that has an error."""
        # Arrange
        job_id = "error-job-456"
        job_dir = temp_data_dir / job_id
        job_dir.mkdir(parents=True)
        
        job_data = {
            "job_id": job_id,
            "status": "error",
            "progress": 0.5,
            "created_at": "2025-11-19T10:00:00Z",
            "updated_at": "2025-11-19T10:02:30Z",
            "page_count": 10,
            "error_message": "OCR processing failed: timeout exceeded",
            "metadata": {"filename": "large-doc.pdf"},
            "pages": []
        }
        
        with open(job_dir / "job_snapshot.json", "w") as f:
            json.dump(job_data, f, indent=2)

        handler = GetJobStatusHandler(job_repository)
        query = GetJobStatusQuery(job_id=job_id)

        # Act
        result = handler.handle(query)

        # Assert
        assert result.status == "error"
        assert result.error_message == "OCR processing failed: timeout exceeded"
        assert result.progress == 0.5

    def test_get_job_status_partial(self, job_repository, temp_data_dir):
        """Test retrieving a partially completed job."""
        # Arrange
        job_id = "partial-job-789"
        job_dir = temp_data_dir / job_id
        job_dir.mkdir(parents=True)
        
        job_data = {
            "job_id": job_id,
            "status": "partial",
            "progress": 0.6,
            "created_at": "2025-11-19T10:00:00Z",
            "updated_at": "2025-11-19T10:03:00Z",
            "page_count": 10,
            "error_message": "Some pages failed to process",
            "metadata": {
                "filename": "mixed-results.pdf",
                "pages_processed": 6,
                "pages_failed": 4,
            },
            "pages": [1, 2, 3, 4, 5, 6]  # 6 processed pages
        }
        
        with open(job_dir / "job_snapshot.json", "w") as f:
            json.dump(job_data, f, indent=2)

        handler = GetJobStatusHandler(job_repository)
        query = GetJobStatusQuery(job_id=job_id)

        # Act
        result = handler.handle(query)

        # Assert
        assert result.status == "partial"
        assert result.progress == 0.6
        assert "failed" in result.error_message.lower()
        assert result.processed_pages == 6
        # Metadata information is not exposed in DTO for security/simplicity
