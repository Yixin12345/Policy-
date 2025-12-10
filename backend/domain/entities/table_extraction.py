"""
TableExtraction Entity - Domain Model for Extracted Table Data

This entity represents a table extracted from a document page. Tables consist of
rows and columns with cell data, metadata, and structural information.

Domain Rules:
- Table must have at least one row and one column
- Each cell has a position (row, column) and content
- Cells can span multiple rows/columns (rowspan, colspan)
- Table has overall confidence score and bounding box
- Headers can be identified separately from data rows
- Empty tables are allowed but flagged
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime

from ..value_objects.confidence import Confidence
from ..value_objects.bounding_box import BoundingBox


@dataclass(frozen=True)
class TableCell:
    """Represents a single cell in a table"""
    row: int
    column: int
    content: str
    rowspan: int = 1
    colspan: int = 1
    is_header: bool = False
    confidence: Optional[Confidence] = None
    bounding_box: Optional[BoundingBox] = None
    
    def __post_init__(self):
        """Validate cell data"""
        if self.row < 0:
            raise ValueError("Row index must be non-negative")
        if self.column < 0:
            raise ValueError("Column index must be non-negative")
        if self.rowspan < 1:
            raise ValueError("Rowspan must be at least 1")
        if self.colspan < 1:
            raise ValueError("Colspan must be at least 1")
    
    def is_empty(self) -> bool:
        """Check if cell content is empty"""
        return not self.content or self.content.strip() == ""
    
    def spans_multiple_cells(self) -> bool:
        """Check if cell spans multiple rows or columns"""
        return self.rowspan > 1 or self.colspan > 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = {
            "row": self.row,
            "column": self.column,
            "content": self.content,
            "rowspan": self.rowspan,
            "colspan": self.colspan,
            "is_header": self.is_header,
        }
        
        if self.confidence:
            data["confidence"] = self.confidence.value
        
        if self.bounding_box:
            data["bounding_box"] = self.bounding_box.to_dict()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TableCell":
        """Create from dictionary"""
        confidence = None
        if "confidence" in data:
            confidence = Confidence(data["confidence"])
        
        bbox = None
        bbox_data = data.get("bounding_box")
        if bbox_data:
            bbox = BoundingBox.from_dict(bbox_data)
        
        return cls(
            row=data.get("row", 0),
            column=data.get("column", 0),
            content=data.get("content", ""),
            rowspan=data.get("rowspan", 1),
            colspan=data.get("colspan", 1),
            is_header=data.get("is_header", False),
            confidence=confidence,
            bounding_box=bbox,
        )


@dataclass
class TableExtraction:
    """
    Domain entity representing an extracted table from a document.
    
    A table consists of cells organized in rows and columns, with optional
    headers, confidence scores, and location information.
    """
    
    id: UUID
    cells: List[TableCell]
    page_number: int
    confidence: Confidence
    bounding_box: Optional[BoundingBox] = None
    title: Optional[str] = None
    num_rows: int = field(init=False)
    num_columns: int = field(init=False)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Calculate dimensions and validate"""
        self._validate()
        self._calculate_dimensions()
    
    def _validate(self):
        """Validate table data"""
        if self.page_number < 1:
            raise ValueError("Page number must be positive")
        
        if not isinstance(self.cells, list):
            raise TypeError("Cells must be a list")
        
        if not all(isinstance(cell, TableCell) for cell in self.cells):
            raise TypeError("All cells must be TableCell instances")
    
    def _calculate_dimensions(self):
        """Calculate number of rows and columns from cells"""
        if not self.cells:
            object.__setattr__(self, 'num_rows', 0)
            object.__setattr__(self, 'num_columns', 0)
        else:
            max_row = max(cell.row + cell.rowspan - 1 for cell in self.cells)
            max_col = max(cell.column + cell.colspan - 1 for cell in self.cells)
            object.__setattr__(self, 'num_rows', max_row + 1)
            object.__setattr__(self, 'num_columns', max_col + 1)
    
    @classmethod
    def create(
        cls,
        cells: List[TableCell],
        page_number: int,
        confidence: float,
        bounding_box: Optional[BoundingBox] = None,
        title: Optional[str] = None,
        table_id: Optional[UUID] = None,
    ) -> "TableExtraction":
        """
        Factory method to create a new table extraction.
        
        Args:
            cells: List of table cells
            page_number: Page number where table is located
            confidence: Overall confidence score (0.0 to 1.0)
            bounding_box: Optional bounding box for table location
            title: Optional table title or caption
            table_id: Optional UUID (generated if not provided)
        
        Returns:
            New TableExtraction instance
        """
        return cls(
            id=table_id or uuid4(),
            cells=cells,
            page_number=page_number,
            confidence=Confidence(confidence),
            bounding_box=bounding_box,
            title=title,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TableExtraction":
        """Create from dictionary representation."""

        raw_cells: List[Dict[str, Any]] = list(data.get("cells", []))

        # Some upstream extractors provide "rows" + "columns" instead of flat cells.
        if not raw_cells and data.get("rows"):
            row_start = data.get("row_start_index", 0)
            columns: List[Dict[str, Any]] = data.get("columns", [])

            if columns:
                for column_index, column in enumerate(columns):
                    header_text = column.get("header") or column.get("key") or ""
                    if header_text:
                        raw_cells.append(
                            {
                                "row": row_start,
                                "column": column_index,
                                "content": header_text,
                                "is_header": True,
                                "confidence": column.get("confidence"),
                            }
                        )

            for row_offset, row in enumerate(data.get("rows", [])):
                if not isinstance(row, list):
                    continue
                for column_index, cell in enumerate(row):
                    if not isinstance(cell, dict):
                        continue
                    value = cell.get("value")
                    cell_entry: Dict[str, Any] = {
                        "row": row_start + (1 if columns else 0) + row_offset,
                        "column": column_index,
                        "content": value if value is not None else "",
                        "confidence": cell.get("confidence"),
                    }
                    if cell.get("bbox"):
                        cell_entry["bounding_box"] = cell["bbox"]
                    raw_cells.append(cell_entry)

        cells = [TableCell.from_dict(cell_data) for cell_data in raw_cells]

        bbox_data = data.get("bounding_box") or data.get("bbox")
        bbox = BoundingBox.from_dict(bbox_data) if bbox_data else None

        raw_id = data.get("id")
        table_id: UUID
        if isinstance(raw_id, UUID):
            table_id = raw_id
        elif isinstance(raw_id, str):
            try:
                table_id = UUID(raw_id)
            except ValueError:
                table_id = uuid4()
        else:
            table_id = uuid4()
        
        table = cls(
            id=table_id,
            cells=cells,
            page_number=data.get("page_number") or data.get("page", 1),
            confidence=Confidence(data.get("confidence", 0.0)),
            bounding_box=bbox,
            title=data.get("title") or data.get("caption"),
        )
        
        if "created_at" in data:
            try:
                object.__setattr__(table, 'created_at', datetime.fromisoformat(data["created_at"]))
            except (TypeError, ValueError):
                pass
        if "updated_at" in data:
            try:
                object.__setattr__(table, 'updated_at', datetime.fromisoformat(data["updated_at"]))
            except (TypeError, ValueError):
                pass
        
        return table
    
    def is_empty(self) -> bool:
        """Check if table has no cells or all cells are empty"""
        return not self.cells or all(cell.is_empty() for cell in self.cells)
    
    def has_headers(self) -> bool:
        """Check if table has header cells"""
        return any(cell.is_header for cell in self.cells)
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if table confidence exceeds threshold"""
        return self.confidence.is_high(threshold)
    
    def needs_review(self, threshold: float = 0.7) -> bool:
        """Check if table needs manual review"""
        return self.confidence.value < threshold
    
    def get_cell(self, row: int, column: int) -> Optional[TableCell]:
        """Get cell at specific position"""
        for cell in self.cells:
            if cell.row == row and cell.column == column:
                return cell
        return None
    
    def get_row(self, row_index: int) -> List[TableCell]:
        """Get all cells in a specific row"""
        return sorted(
            [cell for cell in self.cells if cell.row == row_index],
            key=lambda c: c.column
        )
    
    def get_column(self, column_index: int) -> List[TableCell]:
        """Get all cells in a specific column"""
        return sorted(
            [cell for cell in self.cells if cell.column == column_index],
            key=lambda c: c.row
        )
    
    def get_headers(self) -> List[TableCell]:
        """Get all header cells"""
        return [cell for cell in self.cells if cell.is_header]
    
    def get_data_cells(self) -> List[TableCell]:
        """Get all non-header cells"""
        return [cell for cell in self.cells if not cell.is_header]
    
    def has_spanning_cells(self) -> bool:
        """Check if table has cells that span multiple rows/columns"""
        return any(cell.spans_multiple_cells() for cell in self.cells)
    
    def update_cell(
        self,
        row: int,
        column: int,
        new_content: str,
        new_confidence: Optional[float] = None,
    ) -> "TableExtraction":
        """
        Create new table with updated cell content.
        
        Returns:
            New TableExtraction instance with updated cell
        """
        new_cells = []
        for cell in self.cells:
            if cell.row == row and cell.column == column:
                # Create new cell with updated content
                new_cell = TableCell(
                    row=cell.row,
                    column=cell.column,
                    content=new_content,
                    rowspan=cell.rowspan,
                    colspan=cell.colspan,
                    is_header=cell.is_header,
                    confidence=Confidence(new_confidence) if new_confidence is not None else cell.confidence,
                    bounding_box=cell.bounding_box,
                )
                new_cells.append(new_cell)
            else:
                new_cells.append(cell)
        
        return TableExtraction(
            id=self.id,
            cells=new_cells,
            page_number=self.page_number,
            confidence=self.confidence,
            bounding_box=self.bounding_box,
            title=self.title,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
        )
    
    def add_cell(self, cell: TableCell) -> "TableExtraction":
        """
        Create new table with additional cell.
        
        Returns:
            New TableExtraction instance with added cell
        """
        new_cells = self.cells + [cell]
        
        return TableExtraction(
            id=self.id,
            cells=new_cells,
            page_number=self.page_number,
            confidence=self.confidence,
            bounding_box=self.bounding_box,
            title=self.title,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        data = {
            "id": str(self.id),
            "cells": [cell.to_dict() for cell in self.cells],
            "page_number": self.page_number,
            "confidence": self.confidence.value,
            "num_rows": self.num_rows,
            "num_columns": self.num_columns,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        
        if self.bounding_box:
            data["bounding_box"] = self.bounding_box.to_dict()
        
        if self.title:
            data["title"] = self.title
        
        return data
    
    def to_grid(self) -> List[List[str]]:
        """
        Convert table to 2D grid representation.
        
        Returns:
            2D list of cell contents (simple representation, doesn't handle spans)
        """
        if self.is_empty():
            return []
        
        # Initialize grid with empty strings
        grid = [["" for _ in range(self.num_columns)] for _ in range(self.num_rows)]
        
        # Fill in cell contents
        for cell in self.cells:
            if cell.row < self.num_rows and cell.column < self.num_columns:
                grid[cell.row][cell.column] = cell.content
        
        return grid
    
    def __eq__(self, other: object) -> bool:
        """Tables are equal if they have the same ID"""
        if not isinstance(other, TableExtraction):
            return NotImplemented
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash based on ID for use in sets and dicts"""
        return hash(self.id)
    
    def __repr__(self) -> str:
        """String representation"""
        return (
            f"TableExtraction(id={self.id}, "
            f"rows={self.num_rows}, cols={self.num_columns}, "
            f"cells={len(self.cells)}, page={self.page_number}, "
            f"confidence={self.confidence.value:.2f})"
        )
