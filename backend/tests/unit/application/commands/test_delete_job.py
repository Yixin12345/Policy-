"""
Unit tests for DeleteJob command handler.

Tests the business logic for job deletion including validation,
state checking, and cleanup operations.
"""
import pytest
from unittest.mock import Mock
from dataclasses import dataclass

from backend.application.commands.delete_job import (
    DeleteJobCommand,
    DeleteJobHandler
)
from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.exceptions import EntityNotFoundError, EntityValidationError


@pytest.fixture
def mock_job_repository():
    """Mock job repository."""
    repo = Mock()
    repo.find_by_id = Mock(return_value=None)
    repo.delete = Mock(return_value=None)
    return repo


@pytest.fixture
def sample_job_pending():
    """Sample pending job entity."""
    return Job.create(
        job_id="test_job_123",
        filename="test.pdf",
        source_path="/tmp/test.pdf",
        total_pages=3
    )


@pytest.fixture
def sample_job_completed():
    """Sample completed job entity."""
    job = Job.create(
        job_id="completed_job_456",
        filename="completed.pdf",
        source_path="/tmp/completed.pdf",
        total_pages=2
    )
    return job.mark_completed()


@pytest.fixture
def sample_job_processing():
    """Sample processing job entity."""
    job = Job.create(
        job_id="processing_job_789",
        filename="processing.pdf",
        source_path="/tmp/processing.pdf",
        total_pages=1
    )
    return job.mark_processing()


@pytest.fixture
def sample_job_failed():
    """Sample failed job entity."""
    job = Job.create(
        job_id="failed_job_101",
        filename="failed.pdf",
        source_path="/tmp/failed.pdf",
        total_pages=5
    )
    return job.mark_failed("Processing error")


@pytest.fixture
def handler(mock_job_repository):
    """DeleteJob command handler."""
    return DeleteJobHandler(mock_job_repository)


class TestDeleteJobCommand:
    """Test DeleteJob command creation and validation."""
    
    def test_valid_command_creation(self):
        """Test creating a valid DeleteJob command."""
        command = DeleteJobCommand(job_id="test_job")
        assert command.job_id == "test_job"
    
    def test_command_immutability(self):
        """Test that command is immutable (frozen dataclass)."""
        command = DeleteJobCommand(job_id="test_job")
        with pytest.raises(Exception):  # Should be FrozenInstanceError or AttributeError
            command.job_id = "modified"
    
    def test_empty_job_id_command(self):
        """Test command with empty job ID is still valid (handler validates)."""
        command = DeleteJobCommand(job_id="")
        assert command.job_id == ""


class TestDeleteJobHandler:
    """Test DeleteJob command handler business logic."""
    
    def test_handle_job_not_found(self, handler, mock_job_repository):
        """Test handling when job doesn't exist."""
        mock_job_repository.find_by_id.return_value = None
        
        command = DeleteJobCommand(job_id="nonexistent_job")
        
        with pytest.raises(EntityNotFoundError) as exc_info:
            handler.handle(command)
        
        assert "Job" in str(exc_info.value)
        assert "nonexistent_job" in str(exc_info.value)
        mock_job_repository.find_by_id.assert_called_once_with("nonexistent_job")
        mock_job_repository.delete.assert_not_called()
    
    def test_handle_delete_pending_job_success(self, handler, mock_job_repository, sample_job_pending):
        """Test successful deletion of pending job."""
        mock_job_repository.find_by_id.return_value = sample_job_pending
        
        command = DeleteJobCommand(job_id="test_job_123")
        
        result = handler.handle(command)
        
        mock_job_repository.find_by_id.assert_called_once_with("test_job_123")
        mock_job_repository.delete.assert_called_once_with("test_job_123")
        
        assert result["job_id"] == "test_job_123"
        assert result["deleted"] is True
    
    def test_handle_delete_completed_job_success(self, handler, mock_job_repository, sample_job_completed):
        """Test successful deletion of completed job."""
        mock_job_repository.find_by_id.return_value = sample_job_completed
        
        command = DeleteJobCommand(job_id="completed_job_456")
        
        result = handler.handle(command)
        
        mock_job_repository.find_by_id.assert_called_once_with("completed_job_456")
        mock_job_repository.delete.assert_called_once_with("completed_job_456")
        
        assert result["job_id"] == "completed_job_456"
        assert result["deleted"] is True
    
    def test_handle_delete_failed_job_success(self, handler, mock_job_repository, sample_job_failed):
        """Test successful deletion of failed job."""
        mock_job_repository.find_by_id.return_value = sample_job_failed
        
        command = DeleteJobCommand(job_id="failed_job_101")
        
        result = handler.handle(command)
        
        mock_job_repository.find_by_id.assert_called_once_with("failed_job_101")
        mock_job_repository.delete.assert_called_once_with("failed_job_101")
        
        assert result["job_id"] == "failed_job_101"
        assert result["deleted"] is True
    
    def test_handle_delete_processing_job_error(self, handler, mock_job_repository, sample_job_processing):
        """Test preventing deletion of currently processing job."""
        mock_job_repository.find_by_id.return_value = sample_job_processing
        
        command = DeleteJobCommand(job_id="processing_job_789")
        
        with pytest.raises(EntityValidationError) as exc_info:
            handler.handle(command)
        
        assert "Cannot delete job" in str(exc_info.value)
        assert "running" in str(exc_info.value)
        assert "processing_job_789" in str(exc_info.value)
        
        mock_job_repository.find_by_id.assert_called_once_with("processing_job_789")
        mock_job_repository.delete.assert_not_called()
    
    def test_handle_repository_delete_error(self, handler, mock_job_repository, sample_job_completed):
        """Test handling repository delete errors."""
        mock_job_repository.find_by_id.return_value = sample_job_completed
        mock_job_repository.delete.side_effect = Exception("Database error")
        
        command = DeleteJobCommand(job_id="completed_job_456")
        
        with pytest.raises(Exception) as exc_info:
            handler.handle(command)
        
        assert "Database error" in str(exc_info.value)
        mock_job_repository.find_by_id.assert_called_once_with("completed_job_456")
        mock_job_repository.delete.assert_called_once_with("completed_job_456")
    
    def test_handle_repository_find_error(self, handler, mock_job_repository):
        """Test handling repository find errors."""
        mock_job_repository.find_by_id.side_effect = Exception("Database connection error")
        
        command = DeleteJobCommand(job_id="test_job")
        
        with pytest.raises(Exception) as exc_info:
            handler.handle(command)
        
        assert "Database connection error" in str(exc_info.value)
        mock_job_repository.find_by_id.assert_called_once_with("test_job")
        mock_job_repository.delete.assert_not_called()


class TestDeleteJobHandlerEdgeCases:
    """Test edge cases for DeleteJob handler."""
    
    def test_handle_multiple_deletions_same_job(self, handler, mock_job_repository, sample_job_completed):
        """Test that second deletion attempt fails gracefully."""
        # First call returns the job, second call returns None (job already deleted)
        mock_job_repository.find_by_id.side_effect = [sample_job_completed, None]
        
        command = DeleteJobCommand(job_id="completed_job_456")
        
        # First deletion should succeed
        result1 = handler.handle(command)
        assert result1["deleted"] is True
        
        # Second deletion should fail
        with pytest.raises(EntityNotFoundError):
            handler.handle(command)
        
        # Should have called find_by_id twice and delete once
        assert mock_job_repository.find_by_id.call_count == 2
        mock_job_repository.delete.assert_called_once_with("completed_job_456")
    
    def test_handle_job_status_changes_during_deletion(self, handler, mock_job_repository):
        """Test handling when job status changes between find and delete."""
        # Create a job that starts as completed but changes to processing
        job = Job.create(
            job_id="changing_job",
            filename="test.pdf",
            source_path="/tmp/test.pdf",
            total_pages=1
        ).mark_completed()
        
        # Simulate job changing to processing state after find but before delete
        processing_job = job.mark_processing()
        
        mock_job_repository.find_by_id.return_value = processing_job
        
        command = DeleteJobCommand(job_id="changing_job")
        
        with pytest.raises(EntityValidationError) as exc_info:
            handler.handle(command)
        
        assert "Cannot delete job" in str(exc_info.value)
        assert "running" in str(exc_info.value)
        mock_job_repository.delete.assert_not_called()
    
    def test_handle_whitespace_job_id(self, handler, mock_job_repository):
        """Test handling job ID with whitespace."""
        mock_job_repository.find_by_id.return_value = None
        
        command = DeleteJobCommand(job_id="  whitespace_job  ")
        
        with pytest.raises(EntityNotFoundError):
            handler.handle(command)
        
        # Should pass the exact job_id as provided
        mock_job_repository.find_by_id.assert_called_once_with("  whitespace_job  ")
    
    def test_handle_special_characters_job_id(self, handler, mock_job_repository, sample_job_completed):
        """Test handling job ID with special characters."""
        special_job = Job.create(
            job_id="job-with_special.chars@123",
            filename="special.pdf",
            source_path="/tmp/special.pdf",
            total_pages=1
        ).mark_completed()
        
        mock_job_repository.find_by_id.return_value = special_job
        
        command = DeleteJobCommand(job_id="job-with_special.chars@123")
        
        result = handler.handle(command)
        
        assert result["job_id"] == "job-with_special.chars@123"
        assert result["deleted"] is True
        mock_job_repository.delete.assert_called_once_with("job-with_special.chars@123")