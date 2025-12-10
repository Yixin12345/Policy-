"""
Unit tests for ProcessDocument command handler.

Tests the document processing workflow including file validation,
OCR execution, and result persistence.
"""
import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from dataclasses import dataclass

from backend.application.commands.process_document import (
    ProcessDocumentCommand,
    ProcessDocumentHandler
)
from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.table_extraction import TableExtraction
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.confidence import Confidence
from backend.domain.value_objects.bounding_box import BoundingBox
from backend.domain.exceptions import EntityNotFoundError, EntityValidationError


@pytest.fixture
def mock_job_repository():
    """Mock job repository."""
    repo = Mock()
    repo.find_by_id = Mock(return_value=None)
    repo.save = Mock(return_value=None)
    return repo


@pytest.fixture
def mock_page_repository():
    """Mock page repository."""
    repo = Mock()
    repo.save_page = Mock(return_value=None)
    return repo


@pytest.fixture
def mock_ocr_service():
    """Mock OCR service."""
    service = Mock()
    service.extract_data = Mock(return_value=[])
    return service


@pytest.fixture
def mock_pdf_renderer():
    """Mock PDF renderer."""
    renderer = Mock()
    renderer.get_page_count = Mock(return_value=1)
    return renderer


@pytest.fixture
def mock_mapping_client():
    """Mock mapping client."""
    client = Mock()
    client.map = Mock(return_value=[])
    return client


@pytest.fixture
def sample_job():
    """Sample job entity."""
    return Job.create(
        job_id="test_job_123",
        filename="test.pdf",
        source_path="/tmp/test.pdf",
        total_pages=2
    )


@pytest.fixture
def sample_ocr_results():
    """Sample OCR extraction results."""
    return [
        PageExtraction.create(
            page_number=1,
            fields=[
                FieldExtraction(
                    field_name="invoice_number",
                    value="INV-001",
                    confidence=Confidence(0.95),
                    bounding_box=BoundingBox(x=100, y=200, width=50, height=20)
                )
            ],
            tables=[
                TableExtraction.create(
                    cells=[],
                    page_number=1,
                    confidence=0.90,
                    bounding_box=BoundingBox(50, 100, 200, 100),
                    title="line_items"
                )
            ]
        ),
        PageExtraction.create(
            page_number=2,
            fields=[
                FieldExtraction(
                    field_name="total_amount",
                    value="$1000.00",
                    confidence=Confidence(0.88),
                    bounding_box=BoundingBox(x=200, y=300, width=80, height=25)
                )
            ],
            tables=[]
        )
    ]


@pytest.fixture
def handler(mock_job_repository, mock_page_repository, mock_ocr_service, mock_pdf_renderer, mock_mapping_client):
    """ProcessDocument command handler."""
    return ProcessDocumentHandler(
        mock_job_repository,
        mock_page_repository,
        mock_ocr_service,
        mock_pdf_renderer,
        mock_mapping_client
    )


class TestProcessDocumentCommand:
    """Test ProcessDocument command creation and validation."""
    
    def test_valid_command_creation(self):
        """Test creating a valid ProcessDocument command."""
        command = ProcessDocumentCommand(job_id="test_job", file_path="/path/to/file.pdf")
        assert command.job_id == "test_job"
        assert command.file_path == "/path/to/file.pdf"
    
    def test_command_immutability(self):
        """Test that command is immutable (frozen dataclass)."""
        command = ProcessDocumentCommand(job_id="test_job", file_path="/path/to/file.pdf")
        with pytest.raises(Exception):  # Should be FrozenInstanceError or AttributeError
            command.job_id = "modified"


class TestProcessDocumentHandler:
    """Test ProcessDocument command handler business logic."""
    
    def test_handle_job_not_found(self, handler, mock_job_repository):
        """Test handling when job doesn't exist."""
        mock_job_repository.find_by_id.return_value = None
        
        command = ProcessDocumentCommand(job_id="nonexistent_job", file_path="/tmp/test.pdf")
        
        with pytest.raises(EntityNotFoundError) as exc_info:
            handler.handle(command)
        
        assert "Job" in str(exc_info.value)
        assert "nonexistent_job" in str(exc_info.value)
        mock_job_repository.find_by_id.assert_called_once_with("nonexistent_job")
    
    def test_handle_job_already_processed(self, handler, mock_job_repository, sample_job):
        """Test handling when job is already completed."""
        completed_job = sample_job.mark_completed()
        mock_job_repository.find_by_id.return_value = completed_job
        
        command = ProcessDocumentCommand(job_id="test_job_123", file_path="/tmp/test.pdf")
        
        with pytest.raises(EntityValidationError) as exc_info:
            handler.handle(command)
        
        assert "already processed" in str(exc_info.value).lower()
    
    def test_handle_job_currently_processing(self, handler, mock_job_repository, sample_job):
        """Test handling when job is currently being processed."""
        processing_job = sample_job.mark_processing()
        mock_job_repository.find_by_id.return_value = processing_job
        
        command = ProcessDocumentCommand(job_id="test_job_123", file_path="/tmp/test.pdf")
        
        with pytest.raises(EntityValidationError) as exc_info:
            handler.handle(command)
        
        assert "currently being processed" in str(exc_info.value).lower()
    
    @patch("pathlib.Path.exists")
    def test_handle_file_not_found(self, mock_exists, handler, mock_job_repository, sample_job):
        """Test handling when uploaded file doesn't exist."""
        mock_exists.return_value = False
        mock_job_repository.find_by_id.return_value = sample_job
        
        command = ProcessDocumentCommand(job_id="test_job_123", file_path="/tmp/test.pdf")
        
        with pytest.raises(EntityValidationError) as exc_info:
            handler.handle(command)
        
        assert "file not found" in str(exc_info.value).lower()
        mock_exists.assert_called_once()
    
    @patch("pathlib.Path.exists")
    def test_handle_successful_processing(self, mock_exists, handler, mock_job_repository, mock_page_repository, mock_ocr_service, sample_job, sample_ocr_results):
        """Test successful document processing."""
        mock_exists.return_value = True
        mock_job_repository.find_by_id.return_value = sample_job
        mock_ocr_service.extract_data.return_value = sample_ocr_results
        
        command = ProcessDocumentCommand(job_id="test_job_123", file_path="/tmp/test.pdf")
        
        result = handler.handle(command)
        
        # Verify OCR service called with correct parameters
        mock_ocr_service.extract_data.assert_called_once_with("/tmp/test.pdf")
        
        # Verify pages were saved
        assert mock_page_repository.save_page.call_count == 2
        mock_page_repository.save_page.assert_any_call("test_job_123", sample_ocr_results[0])
        mock_page_repository.save_page.assert_any_call("test_job_123", sample_ocr_results[1])
        
        # Verify job status updated
        saved_calls = mock_job_repository.save.call_args_list
        assert len(saved_calls) >= 2  # At least processing and completed calls
        
        # First call should mark as processing
        processing_job = saved_calls[0][0][0]
        assert processing_job.status == JobStatus.PROCESSING
        
        # Last call should mark as completed
        completed_job = saved_calls[-1][0][0]
        assert completed_job.status == JobStatus.COMPLETED
        
        # Verify result
        assert result["job_id"] == "test_job_123"
        assert result["status"] == "completed"
        assert result["pages_processed"] == 2
        assert "extraction_summary" in result
    
    @patch("pathlib.Path.exists")
    def test_handle_ocr_extraction_error(self, mock_exists, handler, mock_job_repository, mock_page_repository, mock_ocr_service, sample_job):
        """Test handling OCR service errors."""
        mock_exists.return_value = True
        mock_job_repository.find_by_id.return_value = sample_job
        mock_ocr_service.extract_data.side_effect = Exception("OCR processing failed")
        
        command = ProcessDocumentCommand(job_id="test_job_123", file_path="/tmp/test.pdf")
        
        with pytest.raises(Exception) as exc_info:
            handler.handle(command)
        
        assert "OCR processing failed" in str(exc_info.value)
        
        # Verify job was marked as failed
        saved_calls = mock_job_repository.save.call_args_list
        assert len(saved_calls) >= 2
        
        # Should have processing and failed status updates
        failed_job = saved_calls[-1][0][0]
        assert failed_job.status == JobStatus.FAILED
    
    @patch("pathlib.Path.exists")
    def test_handle_empty_ocr_results(self, mock_exists, handler, mock_job_repository, mock_page_repository, mock_ocr_service, sample_job):
        """Test handling when OCR returns no results."""
        mock_exists.return_value = True
        mock_job_repository.find_by_id.return_value = sample_job
        mock_ocr_service.extract_data.return_value = []
        
        command = ProcessDocumentCommand(job_id="test_job_123", file_path="/tmp/test.pdf")
        
        result = handler.handle(command)
        
        # Should still complete successfully
        assert result["job_id"] == "test_job_123"
        assert result["status"] == "completed"
        assert result["pages_processed"] == 0
        
        # No pages should be saved
        mock_page_repository.save_page.assert_not_called()
        
        # Job should be marked as completed
        saved_calls = mock_job_repository.save.call_args_list
        completed_job = saved_calls[-1][0][0]
        assert completed_job.status == JobStatus.COMPLETED
    
    @patch("pathlib.Path.exists")
    def test_handle_partial_ocr_results(self, mock_exists, handler, mock_job_repository, mock_page_repository, mock_ocr_service, sample_job, sample_ocr_results):
        """Test handling when OCR returns fewer pages than expected."""
        mock_exists.return_value = True
        mock_job_repository.find_by_id.return_value = sample_job
        # Return only first page result
        mock_ocr_service.extract_data.return_value = sample_ocr_results[:1]
        
        command = ProcessDocumentCommand(job_id="test_job_123", file_path="/tmp/test.pdf")
        
        result = handler.handle(command)
        
        # Should process available results
        assert result["job_id"] == "test_job_123"
        assert result["status"] == "completed"
        assert result["pages_processed"] == 1
        
        # Only one page should be saved
        mock_page_repository.save_page.assert_called_once()
    
    def test_handle_repository_save_error(self, handler, mock_job_repository, sample_job):
        """Test handling repository save errors."""
        mock_job_repository.find_by_id.return_value = sample_job
        mock_job_repository.save.side_effect = Exception("Database error")
        
        command = ProcessDocumentCommand(job_id="test_job_123", file_path="/tmp/test.pdf")
        
        with pytest.raises(Exception) as exc_info:
            handler.handle(command)
        
        assert "Database error" in str(exc_info.value)
    
    @patch("pathlib.Path.exists")
    def test_handle_page_repository_save_error(self, mock_exists, handler, mock_job_repository, mock_page_repository, mock_ocr_service, sample_job, sample_ocr_results):
        """Test handling page repository save errors."""
        mock_exists.return_value = True
        mock_job_repository.find_by_id.return_value = sample_job
        mock_ocr_service.extract_data.return_value = sample_ocr_results
        mock_page_repository.save_page.side_effect = Exception("Page save error")
        
        command = ProcessDocumentCommand(job_id="test_job_123", file_path="/tmp/test.pdf")
        
        with pytest.raises(Exception) as exc_info:
            handler.handle(command)
        
        assert "Page save error" in str(exc_info.value)
        
        # Job should be marked as failed
        saved_calls = mock_job_repository.save.call_args_list
        failed_job = saved_calls[-1][0][0]
        assert failed_job.status == JobStatus.FAILED