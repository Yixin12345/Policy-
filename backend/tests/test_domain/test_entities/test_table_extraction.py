"""
Tests for TableExtraction Entity and TableCell Value Object
"""

import pytest
from uuid import UUID, uuid4
from datetime import datetime

from domain.entities.table_extraction import TableExtraction, TableCell
from domain.value_objects.confidence import Confidence
from domain.value_objects.bounding_box import BoundingBox


class TestTableCell:
    """Test suite for TableCell value object"""
    
    def test_create_basic_cell(self):
        """Test creating a basic table cell"""
        cell = TableCell(row=0, column=0, content="Header")
        
        assert cell.row == 0
        assert cell.column == 0
        assert cell.content == "Header"
        assert cell.rowspan == 1
        assert cell.colspan == 1
        assert cell.is_header is False
        assert cell.confidence is None
        assert cell.bounding_box is None
    
    def test_create_header_cell(self):
        """Test creating a header cell"""
        cell = TableCell(
            row=0,
            column=1,
            content="Name",
            is_header=True,
            confidence=Confidence(0.95)
        )
        
        assert cell.is_header is True
        assert cell.confidence.value == 0.95
    
    def test_create_spanning_cell(self):
        """Test creating a cell with rowspan and colspan"""
        cell = TableCell(
            row=1,
            column=2,
            content="Merged Cell",
            rowspan=2,
            colspan=3
        )
        
        assert cell.rowspan == 2
        assert cell.colspan == 3
        assert cell.spans_multiple_cells() is True
    
    def test_cell_with_bounding_box(self):
        """Test cell with bounding box"""
        bbox = BoundingBox(x=100, y=200, width=50, height=20)
        cell = TableCell(
            row=0,
            column=0,
            content="Cell",
            bounding_box=bbox
        )
        
        assert cell.bounding_box == bbox
    
    def test_cell_negative_row_raises_error(self):
        """Test that negative row raises ValueError"""
        with pytest.raises(ValueError, match="Row index must be non-negative"):
            TableCell(row=-1, column=0, content="Invalid")
    
    def test_cell_negative_column_raises_error(self):
        """Test that negative column raises ValueError"""
        with pytest.raises(ValueError, match="Column index must be non-negative"):
            TableCell(row=0, column=-1, content="Invalid")
    
    def test_cell_invalid_rowspan_raises_error(self):
        """Test that rowspan < 1 raises ValueError"""
        with pytest.raises(ValueError, match="Rowspan must be at least 1"):
            TableCell(row=0, column=0, content="Invalid", rowspan=0)
    
    def test_cell_invalid_colspan_raises_error(self):
        """Test that colspan < 1 raises ValueError"""
        with pytest.raises(ValueError, match="Colspan must be at least 1"):
            TableCell(row=0, column=0, content="Invalid", colspan=0)
    
    def test_is_empty_true(self):
        """Test is_empty for empty content"""
        cell1 = TableCell(row=0, column=0, content="")
        cell2 = TableCell(row=0, column=0, content="   ")
        
        assert cell1.is_empty() is True
        assert cell2.is_empty() is True
    
    def test_is_empty_false(self):
        """Test is_empty for non-empty content"""
        cell = TableCell(row=0, column=0, content="Data")
        assert cell.is_empty() is False
    
    def test_spans_multiple_cells_true(self):
        """Test spans_multiple_cells returns True for spanning cells"""
        cell1 = TableCell(row=0, column=0, content="Test", rowspan=2)
        cell2 = TableCell(row=0, column=0, content="Test", colspan=3)
        cell3 = TableCell(row=0, column=0, content="Test", rowspan=2, colspan=2)
        
        assert cell1.spans_multiple_cells() is True
        assert cell2.spans_multiple_cells() is True
        assert cell3.spans_multiple_cells() is True
    
    def test_spans_multiple_cells_false(self):
        """Test spans_multiple_cells returns False for single cells"""
        cell = TableCell(row=0, column=0, content="Test")
        assert cell.spans_multiple_cells() is False
    
    def test_cell_to_dict(self):
        """Test converting cell to dictionary"""
        cell = TableCell(
            row=1,
            column=2,
            content="Test Content",
            rowspan=2,
            colspan=1,
            is_header=True,
            confidence=Confidence(0.9),
            bounding_box=BoundingBox(10, 20, 30, 40)
        )
        
        data = cell.to_dict()
        
        assert data["row"] == 1
        assert data["column"] == 2
        assert data["content"] == "Test Content"
        assert data["rowspan"] == 2
        assert data["colspan"] == 1
        assert data["is_header"] is True
        assert data["confidence"] == 0.9
        assert "bounding_box" in data
    
    def test_cell_from_dict(self):
        """Test creating cell from dictionary"""
        data = {
            "row": 0,
            "column": 1,
            "content": "Header",
            "rowspan": 1,
            "colspan": 2,
            "is_header": True,
            "confidence": 0.95,
            "bounding_box": {"x": 10, "y": 20, "width": 30, "height": 40}
        }
        
        cell = TableCell.from_dict(data)
        
        assert cell.row == 0
        assert cell.column == 1
        assert cell.content == "Header"
        assert cell.colspan == 2
        assert cell.is_header is True
        assert cell.confidence.value == 0.95
        assert cell.bounding_box is not None
    
    def test_cell_from_dict_minimal(self):
        """Test creating cell from minimal dictionary"""
        data = {
            "row": 0,
            "column": 0
        }
        
        cell = TableCell.from_dict(data)
        
        assert cell.row == 0
        assert cell.column == 0
        assert cell.content == ""
        assert cell.rowspan == 1
        assert cell.colspan == 1


class TestTableExtraction:
    """Test suite for TableExtraction entity"""
    
    def test_create_basic_table(self):
        """Test creating a basic table"""
        cells = [
            TableCell(0, 0, "A1"),
            TableCell(0, 1, "B1"),
            TableCell(1, 0, "A2"),
            TableCell(1, 1, "B2"),
        ]
        
        table = TableExtraction.create(
            cells=cells,
            page_number=1,
            confidence=0.95
        )
        
        assert len(table.cells) == 4
        assert table.page_number == 1
        assert table.confidence.value == 0.95
        assert table.num_rows == 2
        assert table.num_columns == 2
        assert isinstance(table.id, UUID)
    
    def test_create_with_custom_id(self):
        """Test creating table with custom UUID"""
        custom_id = uuid4()
        cells = [TableCell(0, 0, "Test")]
        
        table = TableExtraction.create(
            cells=cells,
            page_number=1,
            confidence=0.9,
            table_id=custom_id
        )
        
        assert table.id == custom_id
    
    def test_create_with_title_and_bbox(self):
        """Test creating table with title and bounding box"""
        cells = [TableCell(0, 0, "Data")]
        bbox = BoundingBox(10, 20, 100, 50)
        
        table = TableExtraction.create(
            cells=cells,
            page_number=2,
            confidence=0.85,
            bounding_box=bbox,
            title="Sales Data"
        )
        
        assert table.title == "Sales Data"
        assert table.bounding_box == bbox
    
    def test_create_empty_table(self):
        """Test creating an empty table"""
        table = TableExtraction.create(
            cells=[],
            page_number=1,
            confidence=0.5
        )
        
        assert table.num_rows == 0
        assert table.num_columns == 0
        assert table.is_empty() is True
    
    def test_invalid_page_number_raises_error(self):
        """Test that page_number < 1 raises ValueError"""
        with pytest.raises(ValueError, match="Page number must be positive"):
            TableExtraction.create(
                cells=[TableCell(0, 0, "Test")],
                page_number=0,
                confidence=0.9
            )
    
    def test_invalid_cells_type_raises_error(self):
        """Test that non-list cells raises TypeError"""
        with pytest.raises(TypeError, match="Cells must be a list"):
            TableExtraction(
                id=uuid4(),
                cells="not a list",  # type: ignore
                page_number=1,
                confidence=Confidence(0.9)
            )
    
    def test_invalid_cell_items_raises_error(self):
        """Test that non-TableCell items raise TypeError"""
        with pytest.raises(TypeError, match="All cells must be TableCell instances"):
            TableExtraction(
                id=uuid4(),
                cells=[TableCell(0, 0, "Good"), "bad cell"],  # type: ignore
                page_number=1,
                confidence=Confidence(0.9)
            )
    
    def test_dimensions_calculated_correctly(self):
        """Test that num_rows and num_columns are calculated correctly"""
        cells = [
            TableCell(0, 0, "A1"),
            TableCell(0, 2, "C1"),  # Skip column 1
            TableCell(3, 1, "B4"),  # Skip rows 1-2
        ]
        
        table = TableExtraction.create(
            cells=cells,
            page_number=1,
            confidence=0.9
        )
        
        assert table.num_rows == 4  # Rows 0-3
        assert table.num_columns == 3  # Columns 0-2
    
    def test_dimensions_with_spanning_cells(self):
        """Test dimensions with cells that span multiple rows/columns"""
        cells = [
            TableCell(0, 0, "A1", rowspan=2, colspan=2),
            TableCell(0, 2, "C1"),
            TableCell(2, 0, "A3"),
        ]
        
        table = TableExtraction.create(
            cells=cells,
            page_number=1,
            confidence=0.9
        )
        
        # Cell at (0,0) spans to row 1 and column 1
        assert table.num_rows == 3
        assert table.num_columns == 3
    
    def test_is_empty_true_for_no_cells(self):
        """Test is_empty returns True for no cells"""
        table = TableExtraction.create(cells=[], page_number=1, confidence=0.5)
        assert table.is_empty() is True
    
    def test_is_empty_true_for_all_empty_cells(self):
        """Test is_empty returns True when all cells are empty"""
        cells = [
            TableCell(0, 0, ""),
            TableCell(0, 1, "   "),
            TableCell(1, 0, ""),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.5)
        assert table.is_empty() is True
    
    def test_is_empty_false_for_data(self):
        """Test is_empty returns False when cells have content"""
        cells = [
            TableCell(0, 0, ""),
            TableCell(0, 1, "Data"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.5)
        assert table.is_empty() is False
    
    def test_has_headers_true(self):
        """Test has_headers returns True when header cells exist"""
        cells = [
            TableCell(0, 0, "Name", is_header=True),
            TableCell(0, 1, "Age", is_header=True),
            TableCell(1, 0, "John"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        assert table.has_headers() is True
    
    def test_has_headers_false(self):
        """Test has_headers returns False when no headers"""
        cells = [TableCell(0, 0, "Data")]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        assert table.has_headers() is False
    
    def test_is_high_confidence_true(self):
        """Test is_high_confidence returns True for high confidence"""
        cells = [TableCell(0, 0, "Test")]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.95)
        assert table.is_high_confidence() is True
        assert table.is_high_confidence(threshold=0.9) is True
    
    def test_is_high_confidence_false(self):
        """Test is_high_confidence returns False for low confidence"""
        cells = [TableCell(0, 0, "Test")]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.75)
        assert table.is_high_confidence() is False
    
    def test_needs_review_true(self):
        """Test needs_review returns True for low confidence"""
        cells = [TableCell(0, 0, "Test")]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.65)
        assert table.needs_review() is True
        assert table.needs_review(threshold=0.7) is True
    
    def test_needs_review_false(self):
        """Test needs_review returns False for high confidence"""
        cells = [TableCell(0, 0, "Test")]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.85)
        assert table.needs_review() is False
    
    def test_get_cell_found(self):
        """Test get_cell returns cell at position"""
        cells = [
            TableCell(0, 0, "A1"),
            TableCell(0, 1, "B1"),
            TableCell(1, 0, "A2"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        cell = table.get_cell(0, 1)
        assert cell is not None
        assert cell.content == "B1"
    
    def test_get_cell_not_found(self):
        """Test get_cell returns None for missing position"""
        cells = [TableCell(0, 0, "A1")]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        cell = table.get_cell(5, 5)
        assert cell is None
    
    def test_get_row(self):
        """Test get_row returns all cells in row"""
        cells = [
            TableCell(0, 0, "A1"),
            TableCell(0, 2, "C1"),
            TableCell(0, 1, "B1"),
            TableCell(1, 0, "A2"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        row = table.get_row(0)
        assert len(row) == 3
        assert row[0].content == "A1"
        assert row[1].content == "B1"
        assert row[2].content == "C1"
    
    def test_get_column(self):
        """Test get_column returns all cells in column"""
        cells = [
            TableCell(0, 0, "A1"),
            TableCell(2, 0, "A3"),
            TableCell(1, 0, "A2"),
            TableCell(0, 1, "B1"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        col = table.get_column(0)
        assert len(col) == 3
        assert col[0].content == "A1"
        assert col[1].content == "A2"
        assert col[2].content == "A3"
    
    def test_get_headers(self):
        """Test get_headers returns only header cells"""
        cells = [
            TableCell(0, 0, "Name", is_header=True),
            TableCell(0, 1, "Age", is_header=True),
            TableCell(1, 0, "John"),
            TableCell(1, 1, "30"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        headers = table.get_headers()
        assert len(headers) == 2
        assert all(cell.is_header for cell in headers)
    
    def test_get_data_cells(self):
        """Test get_data_cells returns only non-header cells"""
        cells = [
            TableCell(0, 0, "Name", is_header=True),
            TableCell(1, 0, "John"),
            TableCell(1, 1, "30"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        data = table.get_data_cells()
        assert len(data) == 2
        assert all(not cell.is_header for cell in data)
    
    def test_has_spanning_cells_true(self):
        """Test has_spanning_cells returns True when spanning cells exist"""
        cells = [
            TableCell(0, 0, "Merged", rowspan=2),
            TableCell(0, 1, "Data"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        assert table.has_spanning_cells() is True
    
    def test_has_spanning_cells_false(self):
        """Test has_spanning_cells returns False for regular table"""
        cells = [
            TableCell(0, 0, "A1"),
            TableCell(0, 1, "B1"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        assert table.has_spanning_cells() is False
    
    def test_update_cell(self):
        """Test update_cell creates new table with updated content"""
        cells = [
            TableCell(0, 0, "Old"),
            TableCell(0, 1, "Data"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        new_table = table.update_cell(0, 0, "New")
        
        assert new_table.id == table.id
        assert new_table is not table
        assert new_table.get_cell(0, 0).content == "New"
        assert new_table.get_cell(0, 1).content == "Data"
        assert table.get_cell(0, 0).content == "Old"  # Original unchanged
    
    def test_add_cell(self):
        """Test add_cell creates new table with additional cell"""
        cells = [TableCell(0, 0, "A1")]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        new_cell = TableCell(0, 1, "B1")
        new_table = table.add_cell(new_cell)
        
        assert len(new_table.cells) == 2
        assert len(table.cells) == 1  # Original unchanged
        assert new_table.get_cell(0, 1).content == "B1"
    
    def test_to_dict(self):
        """Test converting table to dictionary"""
        cells = [
            TableCell(0, 0, "Header", is_header=True),
            TableCell(1, 0, "Data"),
        ]
        bbox = BoundingBox(10, 20, 100, 50)
        
        table = TableExtraction.create(
            cells=cells,
            page_number=2,
            confidence=0.95,
            bounding_box=bbox,
            title="Test Table"
        )
        
        data = table.to_dict()
        
        assert data["page_number"] == 2
        assert data["confidence"] == 0.95
        assert data["num_rows"] == 2
        assert data["num_columns"] == 1
        assert data["title"] == "Test Table"
        assert "bounding_box" in data
        assert len(data["cells"]) == 2
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_from_dict(self):
        """Test creating table from dictionary"""
        data = {
            "id": str(uuid4()),
            "cells": [
                {"row": 0, "column": 0, "content": "A1", "is_header": True},
                {"row": 1, "column": 0, "content": "A2"},
            ],
            "page_number": 1,
            "confidence": 0.9,
            "title": "Test",
            "bounding_box": {"x": 10, "y": 20, "width": 100, "height": 50},
        }
        
        table = TableExtraction.from_dict(data)
        
        assert str(table.id) == data["id"]
        assert len(table.cells) == 2
        assert table.page_number == 1
        assert table.confidence.value == 0.9
        assert table.title == "Test"
        assert table.bounding_box is not None
    
    def test_from_dict_minimal(self):
        """Test creating table from minimal dictionary"""
        data = {
            "cells": [],
            "page_number": 1,
            "confidence": 0.5,
        }
        
        table = TableExtraction.from_dict(data)
        
        assert isinstance(table.id, UUID)
        assert len(table.cells) == 0
        assert table.title is None
        assert table.bounding_box is None
    
    def test_to_grid(self):
        """Test converting table to 2D grid"""
        cells = [
            TableCell(0, 0, "A1"),
            TableCell(0, 1, "B1"),
            TableCell(1, 0, "A2"),
            TableCell(1, 1, "B2"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        grid = table.to_grid()
        
        assert grid == [
            ["A1", "B1"],
            ["A2", "B2"],
        ]
    
    def test_to_grid_sparse(self):
        """Test to_grid with sparse cells (missing positions)"""
        cells = [
            TableCell(0, 0, "A1"),
            TableCell(0, 2, "C1"),
            TableCell(2, 1, "B3"),
        ]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        grid = table.to_grid()
        
        assert grid[0][0] == "A1"
        assert grid[0][1] == ""
        assert grid[0][2] == "C1"
        assert grid[1][0] == ""
        assert grid[2][1] == "B3"
    
    def test_to_grid_empty_table(self):
        """Test to_grid for empty table"""
        table = TableExtraction.create(cells=[], page_number=1, confidence=0.5)
        grid = table.to_grid()
        assert grid == []
    
    def test_equality_same_id(self):
        """Test tables with same ID are equal"""
        table_id = uuid4()
        cells = [TableCell(0, 0, "Test")]
        
        table1 = TableExtraction.create(cells=cells, page_number=1, confidence=0.9, table_id=table_id)
        table2 = TableExtraction.create(cells=cells, page_number=2, confidence=0.5, table_id=table_id)
        
        assert table1 == table2
    
    def test_equality_different_id(self):
        """Test tables with different IDs are not equal"""
        cells = [TableCell(0, 0, "Test")]
        
        table1 = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        table2 = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        assert table1 != table2
    
    def test_hash_consistency(self):
        """Test hash is consistent for use in sets/dicts"""
        cells = [TableCell(0, 0, "Test")]
        table = TableExtraction.create(cells=cells, page_number=1, confidence=0.9)
        
        table_set = {table}
        assert table in table_set
        assert hash(table) == hash(table.id)
    
    def test_repr(self):
        """Test string representation"""
        cells = [
            TableCell(0, 0, "A1"),
            TableCell(0, 1, "B1"),
            TableCell(1, 0, "A2"),
        ]
        table = TableExtraction.create(cells=cells, page_number=3, confidence=0.87)
        
        repr_str = repr(table)
        
        assert "TableExtraction" in repr_str
        assert "rows=2" in repr_str
        assert "cols=2" in repr_str
        assert "cells=3" in repr_str
        assert "page=3" in repr_str
        assert "0.87" in repr_str
