"""
Data Transfer Objects for Page-related queries.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass(frozen=True)
class FieldDTO:
    """DTO for field extraction."""
    
    name: str
    value: str
    confidence: float
    bbox: Optional[Dict[str, float]] = None
    was_edited: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DTO to dictionary."""
        result: Dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "confidence": self.confidence,
            "was_edited": self.was_edited,
        }
        if self.bbox is not None:
            result["bbox"] = self.bbox
        return result


@dataclass(frozen=True)
class TableCellDTO:
    """DTO for table cell."""
    
    row: int
    col: int
    value: str
    confidence: float
    row_span: int = 1
    col_span: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "row": self.row,
            "col": self.col,
            "value": self.value,
            "confidence": self.confidence,
            "row_span": self.row_span,
            "col_span": self.col_span,
        }


@dataclass(frozen=True)
class TableDTO:
    """DTO for table extraction."""
    
    title: str
    cells: List[TableCellDTO]
    bbox: Optional[Dict[str, float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DTO to dictionary."""
        result: Dict[str, Any] = {
            "title": self.title,
            "cells": [cell.to_dict() for cell in self.cells],
        }
        if self.bbox is not None:
            result["bbox"] = self.bbox
        return result


@dataclass(frozen=True)
class PageDataDTO:
    """DTO for complete page data."""
    
    job_id: str
    page_number: int
    fields: List[FieldDTO]
    tables: List[TableDTO]
    overall_confidence: float
    needs_review: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "job_id": self.job_id,
            "page_number": self.page_number,
            "fields": [field.to_dict() for field in self.fields],
            "tables": [table.to_dict() for table in self.tables],
            "overall_confidence": self.overall_confidence,
            "needs_review": self.needs_review,
        }
