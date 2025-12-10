"""
Unit tests for GetPageData query handler.

Tests the query handler with a mocked repository to ensure:
- Successful page retrieval
- Proper DTO mapping for fields and tables
- Error handling for not found pages
"""
import pytest
from unittest.mock import Mock

from backend.application.queries.get_page_data import (
    GetPageDataQuery,
    GetPageDataHandler,
)
from backend.application.dto.page_dto import PageDataDTO
from backend.domain.exceptions import EntityNotFoundError
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.table_extraction import TableExtraction, TableCell
from backend.domain.value_objects.confidence import Confidence
from backend.domain.value_objects.bounding_box import BoundingBox


class TestGetPageDataHandler:
    """Test cases for GetPageDataHandler."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create a mock page repository."""
        return Mock()
    
    @pytest.fixture
    def handler(self, mock_repository):
        """Create handler with mocked repository."""
        return GetPageDataHandler(mock_repository)
    
    @pytest.fixture
    def sample_page(self):
        """Create a sample page with fields and tables."""
        fields = [
            FieldExtraction.create(
                field_name="invoice_number",
                value="INV-001",
                confidence=0.95,
                bounding_box=BoundingBox(0.1, 0.1, 0.3, 0.05),
            ),
            FieldExtraction.create(
                field_name="total",
                value="$1,234.56",
                confidence=0.88,
                bounding_box=BoundingBox(0.7, 0.8, 0.2, 0.05),
            ).update_value("$1,234.56"),  # Mark as edited
        ]
        
        cells = [
            TableCell(row=0, column=0, content="Description", confidence=Confidence(0.92)),
            TableCell(row=0, column=1, content="Amount", confidence=Confidence(0.91)),
            TableCell(row=1, column=0, content="Service A", confidence=Confidence(0.90)),
            TableCell(row=1, column=1, content="$100", confidence=Confidence(0.89)),
        ]
        
        tables = [
            TableExtraction.create(
                cells=cells,
                page_number=1,
                confidence=0.90,
                bounding_box=BoundingBox(0.1, 0.3, 0.8, 0.4),
                title="Line Items",
            ),
        ]
        
        return PageExtraction.create(
            page_number=1,
            fields=fields,
            tables=tables,
        )
    
    def test_handle_returns_page_data_dto(self, handler, mock_repository, sample_page):
        """Test successful query returns PageDataDTO."""
        # Arrange
        query = GetPageDataQuery(job_id="job-123", page_number=1)
        mock_repository.find_page.return_value = sample_page
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert isinstance(result, PageDataDTO)
        assert result.job_id == "job-123"
        assert result.page_number == 1
        assert len(result.fields) == 2
        assert len(result.tables) == 1
        mock_repository.find_page.assert_called_once_with("job-123", 1)
    
    def test_handle_maps_field_data_correctly(self, handler, mock_repository, sample_page):
        """Test field data is correctly mapped to DTOs."""
        # Arrange
        query = GetPageDataQuery(job_id="job-123", page_number=1)
        mock_repository.find_page.return_value = sample_page
        
        # Act
        result = handler.handle(query)
        
        # Assert - First field
        field1 = result.fields[0]
        assert field1.name == "invoice_number"
        assert field1.value == "INV-001"
        assert field1.confidence == 0.95
        assert field1.bbox == {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.05}
        assert field1.was_edited is False
        
        # Assert - Second field (edited)
        field2 = result.fields[1]
        assert field2.name == "total"
        assert field2.value == "$1,234.56"
        assert field2.confidence == 0.88
        assert field2.was_edited is True
    
    def test_handle_maps_table_data_correctly(self, handler, mock_repository, sample_page):
        """Test table data is correctly mapped to DTOs."""
        # Arrange
        query = GetPageDataQuery(job_id="job-123", page_number=1)
        mock_repository.find_page.return_value = sample_page
        
        # Act
        result = handler.handle(query)
        
        # Assert - Table metadata
        table = result.tables[0]
        assert table.title == "Line Items"
        assert table.bbox == {"x": 0.1, "y": 0.3, "width": 0.8, "height": 0.4}
        assert len(table.cells) == 4
        
        # Assert - Table cells
        cell1 = table.cells[0]
        assert cell1.row == 0
        assert cell1.col == 0
        assert cell1.value == "Description"
        assert cell1.confidence == 0.92
        assert cell1.row_span == 1
        assert cell1.col_span == 1
    
    def test_handle_calculates_overall_confidence(self, handler, mock_repository, sample_page):
        """Test overall confidence is calculated."""
        # Arrange
        query = GetPageDataQuery(job_id="job-123", page_number=1)
        mock_repository.find_page.return_value = sample_page
        
        # Act
        result = handler.handle(query)
        
        # Assert - Should be average of all confidences
        # Fields: 0.95, 0.88
        # Table cells: 0.92, 0.91, 0.90, 0.89
        # Average: (0.95 + 0.88 + 0.92 + 0.91 + 0.90 + 0.89) / 6 ≈ 0.908
        assert 0.90 <= result.overall_confidence <= 0.92
    
    def test_handle_determines_needs_review(self, handler, mock_repository):
        """Test needs_review flag is set correctly."""
        # Arrange - Page with low confidence field
        page = PageExtraction.create(
            page_number=1,
            fields=[
                FieldExtraction.create(
                    field_name="uncertain",
                    value="maybe",
                    confidence=0.45,  # Low confidence
                ),
            ],
            tables=[],
        )
        query = GetPageDataQuery(job_id="job-123", page_number=1)
        mock_repository.find_page.return_value = page
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert result.needs_review is True
    
    def test_handle_with_empty_page(self, handler, mock_repository):
        """Test handling page with no fields or tables."""
        # Arrange
        page = PageExtraction.create(page_number=1, fields=[], tables=[])
        query = GetPageDataQuery(job_id="job-123", page_number=1)
        mock_repository.find_page.return_value = page
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert result.page_number == 1
        assert len(result.fields) == 0
        assert len(result.tables) == 0
        assert result.overall_confidence == 1.0  # Empty pages are "perfect"
        assert result.needs_review is False
    
    def test_handle_raises_not_found_when_page_missing(self, handler, mock_repository):
        """Test raises EntityNotFoundError when page doesn't exist."""
        # Arrange
        query = GetPageDataQuery(job_id="job-123", page_number=99)
        mock_repository.find_page.return_value = None
        
        # Act & Assert
        with pytest.raises(EntityNotFoundError) as exc_info:
            handler.handle(query)
        
        assert "job-123" in str(exc_info.value)
        assert "99" in str(exc_info.value)
        mock_repository.find_page.assert_called_once_with("job-123", 99)
    
    def test_handle_with_fields_without_bbox(self, handler, mock_repository):
        """Test fields without bounding boxes are handled correctly."""
        # Arrange
        page = PageExtraction.create(
            page_number=1,
            fields=[
                FieldExtraction.create(
                    field_name="no_bbox",
                    value="value",
                    confidence=0.9,
                    bounding_box=None,  # No bbox
                ),
            ],
            tables=[],
        )
        query = GetPageDataQuery(job_id="job-123", page_number=1)
        mock_repository.find_page.return_value = page
        
        # Act
        result = handler.handle(query)
        
        # Assert
        assert result.fields[0].bbox is None
    
    def test_query_is_immutable(self):
        """Test query object is immutable."""
        query = GetPageDataQuery(job_id="test", page_number=1)
        
        with pytest.raises(AttributeError):
            query.job_id = "changed"  # type: ignore
