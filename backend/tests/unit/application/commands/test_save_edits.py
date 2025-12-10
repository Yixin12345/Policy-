"""
Unit tests for SaveEdits command handler.

Tests the business logic for saving user edits to field and table data,
including validation, error handling, and repository interactions.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from dataclasses import dataclass
from typing import List, Dict, Any

from backend.application.commands.save_edits import (
    SaveEditsCommand,
    SaveEditsHandler,
    FieldEdit,
    TableCellEdit
)
from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.table_extraction import TableExtraction, TableCell
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
    repo.find_page = Mock(return_value=None)
    repo.save_page = Mock(return_value=None)
    return repo


@pytest.fixture
def sample_job():
    """Sample job entity."""
    return Job.create(
        job_id="test_job_123",
        filename="test.pdf",
        source_path="/tmp/test.pdf",
        total_pages=3
    )


@pytest.fixture
def sample_page():
    """Sample page extraction entity."""
    fields = [
        FieldExtraction(
            field_name="invoice_number",
            value="INV-001",
            confidence=Confidence(0.95),
            bounding_box=BoundingBox(x=100, y=200, width=50, height=20)
        ),
        FieldExtraction(
            field_name="total_amount",
            value="$1000.00",
            confidence=Confidence(0.90),
            bounding_box=BoundingBox(x=200, y=300, width=80, height=25)
        )
    ]
    
    table_cells = [
        TableCell(row=0, column=0, content="Product A", confidence=Confidence(0.95), bounding_box=BoundingBox(50, 100, 100, 20)),
        TableCell(row=0, column=1, content="2", confidence=Confidence(0.90), bounding_box=BoundingBox(150, 100, 50, 20)),
        TableCell(row=0, column=2, content="$50.00", confidence=Confidence(0.85), bounding_box=BoundingBox(200, 100, 80, 20))
    ]
    
    tables = [
        TableExtraction.create(
            cells=table_cells,
            page_number=1,
            confidence=0.90,
            bounding_box=BoundingBox(50, 100, 300, 100),
            title="line_items"
        )
    ]
    
    return PageExtraction.create(page_number=1, fields=fields, tables=tables)


@pytest.fixture
def handler(mock_job_repository, mock_page_repository):
    """SaveEdits command handler."""
    return SaveEditsHandler(mock_job_repository, mock_page_repository)


class TestSaveEditsCommand:
    """Test SaveEdits command creation and validation."""
    
    def test_valid_command_creation(self):
        """Test creating a valid SaveEdits command."""
        field_edits = [FieldEdit(page_number=1, field_name="test", new_value="value")]
        command = SaveEditsCommand(
            job_id="test_job",
            field_edits=field_edits,
            table_cell_edits=[]
        )
        assert command.job_id == "test_job"
        assert len(command.field_edits) == 1
        assert len(command.table_cell_edits) == 0
    
    def test_empty_edits_command(self):
        """Test command with no edits is valid (handler decides what to do)."""
        command = SaveEditsCommand(
            job_id="test_job",
            field_edits=[],
            table_cell_edits=[]
        )
        assert command.job_id == "test_job"
        assert len(command.field_edits) == 0
        assert len(command.table_cell_edits) == 0


class TestSaveEditsHandler:
    """Test SaveEdits command handler business logic."""
    
    def test_handle_job_not_found(self, handler, mock_job_repository):
        """Test handling when job doesn't exist."""
        mock_job_repository.find_by_id.return_value = None
        
        command = SaveEditsCommand(
            job_id="nonexistent_job",
            field_edits=[FieldEdit(page_number=1, field_name="test", new_value="value")],
            table_cell_edits=[]
        )
        
        with pytest.raises(EntityNotFoundError) as exc_info:
            handler.handle(command)
        
        assert "Job" in str(exc_info.value)
        assert "nonexistent_job" in str(exc_info.value)
    
    def test_handle_page_not_found(self, handler, mock_job_repository, mock_page_repository, sample_job):
        """Test handling when page doesn't exist."""
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page.return_value = None
        
        command = SaveEditsCommand(
            job_id="test_job_123",
            field_edits=[FieldEdit(page_number=99, field_name="test", new_value="value")],
            table_cell_edits=[]
        )
        
        with pytest.raises(EntityNotFoundError) as exc_info:
            handler.handle(command)
        
        assert "Page" in str(exc_info.value)
    
    def test_handle_field_not_found(self, handler, mock_job_repository, mock_page_repository, sample_job, sample_page):
        """Test handling when field doesn't exist."""
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page.return_value = sample_page
        
        command = SaveEditsCommand(
            job_id="test_job_123",
            field_edits=[FieldEdit(page_number=1, field_name="nonexistent_field", new_value="value")],
            table_cell_edits=[]
        )
        
        with pytest.raises(EntityNotFoundError) as exc_info:
            handler.handle(command)
        
        assert "FieldExtraction" in str(exc_info.value)
        assert "nonexistent_field" in str(exc_info.value)
    
    def test_handle_successful_field_edit(self, handler, mock_job_repository, mock_page_repository, sample_job, sample_page):
        """Test successful field value update."""
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page.return_value = sample_page
        
        command = SaveEditsCommand(
            job_id="test_job_123",
            field_edits=[FieldEdit(page_number=1, field_name="invoice_number", new_value="INV-002")],
            table_cell_edits=[]
        )
        
        result = handler.handle(command)
        
        # Verify repository calls
        assert mock_job_repository.find_by_id.call_count == 2  # Called at start and end
        mock_job_repository.find_by_id.assert_any_call("test_job_123")
        mock_page_repository.find_page.assert_called_once_with("test_job_123", 1)
        mock_page_repository.save_page.assert_called_once()
        
        # Verify result
        assert result["job_id"] == "test_job_123"
        assert result["field_edits_applied"] == 1
        assert result["table_cell_edits_applied"] == 0
        assert result["pages_modified"] == 1
    
    def test_handle_successful_table_cell_edit(self, handler, mock_job_repository, mock_page_repository, sample_job, sample_page):
        """Test successful table cell update."""
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page.return_value = sample_page
        
        command = SaveEditsCommand(
            job_id="test_job_123",
            field_edits=[],
            table_cell_edits=[TableCellEdit(page_number=1, row=0, column=1, new_value="3")]
        )
        
        result = handler.handle(command)
        
        # Verify result
        assert result["job_id"] == "test_job_123"
        assert result["field_edits_applied"] == 0
        assert result["table_cell_edits_applied"] == 1
        assert result["pages_modified"] == 1
    
    def test_handle_multiple_edits_same_page(self, handler, mock_job_repository, mock_page_repository, sample_job, sample_page):
        """Test multiple edits on the same page."""
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page.return_value = sample_page
        
        command = SaveEditsCommand(
            job_id="test_job_123",
            field_edits=[
                FieldEdit(page_number=1, field_name="invoice_number", new_value="INV-002"),
                FieldEdit(page_number=1, field_name="total_amount", new_value="$2000.00")
            ],
            table_cell_edits=[
                TableCellEdit(page_number=1, row=0, column=1, new_value="3")
            ]
        )
        
        result = handler.handle(command)
        
        # Should process page only once
        mock_page_repository.find_page.assert_called_once_with("test_job_123", 1)
        mock_page_repository.save_page.assert_called_once()
        
        assert result["field_edits_applied"] == 2
        assert result["table_cell_edits_applied"] == 1
        assert result["pages_modified"] == 1
    
    def test_handle_multiple_pages(self, handler, mock_job_repository, mock_page_repository, sample_job, sample_page):
        """Test edits across multiple pages."""
        page1 = sample_page
        page2 = PageExtraction.create(
            page_number=2,
            fields=[
                FieldExtraction(
                    field_name="date",
                    value="2023-01-01",
                    confidence=Confidence(0.95),
                    bounding_box=BoundingBox(x=100, y=50, width=80, height=20)
                )
            ],
            tables=[]
        )
        
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page.side_effect = lambda job_id, page_num: page1 if page_num == 1 else page2
        
        command = SaveEditsCommand(
            job_id="test_job_123",
            field_edits=[
                FieldEdit(page_number=1, field_name="invoice_number", new_value="INV-002"),
                FieldEdit(page_number=2, field_name="date", new_value="2023-01-02")
            ],
            table_cell_edits=[]
        )
        
        result = handler.handle(command)
        
        # Should call find_page for both pages
        assert mock_page_repository.find_page.call_count == 2
        assert mock_page_repository.save_page.call_count == 2
        
        assert result["field_edits_applied"] == 2
        assert result["table_cell_edits_applied"] == 0
        assert result["pages_modified"] == 2
    
    def test_handle_table_cell_out_of_bounds(self, handler, mock_job_repository, mock_page_repository, sample_job, sample_page):
        """Test handling invalid table cell coordinates."""
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page.return_value = sample_page
        
        command = SaveEditsCommand(
            job_id="test_job_123",
            field_edits=[],
            table_cell_edits=[TableCellEdit(page_number=1, row=5, column=5, new_value="invalid")]
        )
        
        with pytest.raises(EntityNotFoundError) as exc_info:
            handler.handle(command)
        
        assert "TableCell" in str(exc_info.value)
    
    def test_handle_no_tables_on_page(self, handler, mock_job_repository, mock_page_repository, sample_job):
        """Test handling table edits when page has no tables."""
        page_no_tables = PageExtraction.create(
            page_number=1,
            fields=[],
            tables=[]
        )
        
        mock_job_repository.find_by_id.return_value = sample_job
        mock_page_repository.find_page.return_value = page_no_tables
        
        command = SaveEditsCommand(
            job_id="test_job_123",
            field_edits=[],
            table_cell_edits=[TableCellEdit(page_number=1, row=0, column=0, new_value="test")]
        )
        
        with pytest.raises(EntityNotFoundError) as exc_info:
            handler.handle(command)
        
        assert "TableExtraction" in str(exc_info.value)