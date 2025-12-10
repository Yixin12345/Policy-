"""
Domain Entity: PageExtraction

Represents all extraction data for a single page in a document.
Aggregates field and table extractions with page metadata.
"""

from dataclasses import dataclass, replace
from typing import Optional

from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.table_extraction import TableExtraction
from backend.domain.value_objects.confidence import Confidence


@dataclass(frozen=True)
class PageExtraction:
    """
    Represents all extractions from a single document page.
    
    Business rules:
    - Page numbers are 1-indexed
    - A page can have zero or more field extractions
    - A page can have zero or more table extractions
    - Overall confidence is calculated from all extractions
    - Pages track whether they have been reviewed/edited
    """
    
    page_number: int
    fields: tuple[FieldExtraction, ...]
    tables: tuple[TableExtraction, ...]
    
    # Metadata
    image_path: Optional[str] = None
    has_edits: bool = False
    status: str = "completed"
    markdown_text: Optional[str] = None
    image_mime: Optional[str] = None
    rotation_applied: int = 0
    document_type_hint: Optional[str] = None
    document_type_confidence: Optional[float] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        """Validate page extraction data."""
        if self.page_number < 1:
            raise ValueError("Page number must be >= 1")
        
        # Ensure fields and tables are tuples (immutable)
        if not isinstance(self.fields, tuple):
            object.__setattr__(self, 'fields', tuple(self.fields))
        if not isinstance(self.tables, tuple):
            object.__setattr__(self, 'tables', tuple(self.tables))
    
    # ==================== Factory Methods ====================
    
    @classmethod
    def create(
        cls,
        page_number: int,
        fields: list[FieldExtraction] | None = None,
        tables: list[TableExtraction] | None = None,
        image_path: str | None = None,
        *,
        status: str = "completed",
        markdown_text: str | None = None,
        image_mime: str | None = None,
        rotation_applied: int = 0,
        document_type_hint: str | None = None,
        document_type_confidence: float | None = None,
        error_message: str | None = None,
        has_edits: bool = False,
    ) -> "PageExtraction":
        """Create a new PageExtraction."""
        return cls(
            page_number=page_number,
            fields=tuple(fields or []),
            tables=tuple(tables or []),
            image_path=image_path,
            has_edits=has_edits,
            status=status,
            markdown_text=markdown_text,
            image_mime=image_mime,
            rotation_applied=rotation_applied,
            document_type_hint=document_type_hint,
            document_type_confidence=document_type_confidence,
            error_message=error_message,
        )
    
    @classmethod
    def from_dict(cls, data: dict) -> "PageExtraction":
        """Create PageExtraction from dictionary."""

        markdown_text = data.get("markdown_text")
        if markdown_text is None:
            markdown_text = data.get("markdownText")

        image_mime = data.get("image_mime")
        if image_mime is None:
            image_mime = data.get("imageMime")

        rotation_value = data.get("rotation_applied")
        if rotation_value is None:
            rotation_value = data.get("rotationApplied")
        try:
            rotation_applied = int(rotation_value) if rotation_value is not None else 0
        except (TypeError, ValueError):
            rotation_applied = 0

        document_type_hint = data.get("document_type_hint")
        if document_type_hint is None:
            document_type_hint = data.get("documentTypeHint")

        document_type_confidence = data.get("document_type_confidence")
        if document_type_confidence is None:
            document_type_confidence = data.get("documentTypeConfidence")
        if document_type_confidence is not None:
            try:
                document_type_confidence = float(document_type_confidence)
            except (TypeError, ValueError):
                document_type_confidence = None

        error_message = data.get("error_message")
        if error_message is None:
            error_message = data.get("errorMessage")

        return cls(
            page_number=data["page_number"],
            fields=tuple(
                FieldExtraction.from_dict(f) for f in data.get("fields", [])
            ),
            tables=tuple(
                TableExtraction.from_dict(t) for t in data.get("tables", [])
            ),
            image_path=data.get("image_path"),
            has_edits=data.get("has_edits", data.get("hasEdits", False)),
            status=data.get("status", "completed"),
            markdown_text=markdown_text,
            image_mime=image_mime,
            rotation_applied=rotation_applied,
            document_type_hint=document_type_hint,
            document_type_confidence=document_type_confidence,
            error_message=error_message,
        )
    
    # ==================== Query Methods ====================
    
    @property
    def total_extractions(self) -> int:
        """Total number of extractions (fields + tables) on this page."""
        return len(self.fields) + len(self.tables)
    
    @property
    def has_fields(self) -> bool:
        """Check if this page has any field extractions."""
        return len(self.fields) > 0
    
    @property
    def has_tables(self) -> bool:
        """Check if this page has any table extractions."""
        return len(self.tables) > 0
    
    @property
    def is_empty(self) -> bool:
        """Check if this page has no extractions."""
        return self.total_extractions == 0
    
    @property
    def overall_confidence(self) -> Confidence:
        """Calculate average confidence across all extractions on this page."""
        if self.is_empty:
            return Confidence(1.0)  # Empty pages are "perfect"
        
        confidences = []
        
        # Collect field confidences
        for field in self.fields:
            confidences.append(field.confidence.value)
        
        # Collect table confidences
        for table in self.tables:
            confidences.append(table.confidence.value)
        
        avg_confidence = sum(confidences) / len(confidences)
        return Confidence(avg_confidence)
    
    def get_field_by_name(self, field_name: str) -> Optional[FieldExtraction]:
        """Find a field by its exact name."""
        for field in self.fields:
            if field.field_name == field_name:
                return field
        return None
    
    def get_table_by_title(self, title: str) -> Optional[TableExtraction]:
        """Find a table by its exact title."""
        for table in self.tables:
            if table.title == title:
                return table
        return None
    
    @property
    def low_confidence_count(self) -> int:
        """Count extractions with low confidence on this page."""
        count = 0
        threshold = 0.5
        
        # Count low-confidence fields
        for field in self.fields:
            if field.is_low_confidence(threshold):
                count += 1
        
        # Count low-confidence tables (using confidence value directly)
        for table in self.tables:
            if table.confidence.value < threshold:
                count += 1
        
        return count
    
    def has_low_confidence_items(self, threshold: float = 0.5) -> bool:
        """Check if this page has any low confidence extractions."""
        return self.low_confidence_count > 0
    
    def needs_review(self) -> bool:
        """Determine if this page needs manual review."""
        return self.has_low_confidence_items() and not self.has_edits
    
    # ==================== Mutation Methods ====================
    
    def update_field(self, field_name: str, new_field: FieldExtraction) -> "PageExtraction":
        """Replace a field by name with an updated version."""
        updated_fields = []
        field_found = False
        
        for field in self.fields:
            if field.field_name == field_name:
                updated_fields.append(new_field)
                field_found = True
            else:
                updated_fields.append(field)
        
        if not field_found:
            raise ValueError(f"Field '{field_name}' not found on page {self.page_number}")
        
        return replace(
            self,
            fields=tuple(updated_fields),
            has_edits=True,
        )
    
    def update_table(self, table_title: str, new_table: TableExtraction) -> "PageExtraction":
        """Replace a table by title with an updated version."""
        updated_tables = []
        table_found = False
        
        for table in self.tables:
            if table.title == table_title:
                updated_tables.append(new_table)
                table_found = True
            else:
                updated_tables.append(table)
        
        if not table_found:
            raise ValueError(f"Table '{table_title}' not found on page {self.page_number}")
        
        return replace(
            self,
            tables=tuple(updated_tables),
            has_edits=True,
        )
    
    def add_field(self, field: FieldExtraction) -> "PageExtraction":
        """Add a new field extraction to this page."""
        # Check for duplicate field names
        if self.get_field_by_name(field.field_name) is not None:
            raise ValueError(f"Field '{field.field_name}' already exists on page {self.page_number}")
        
        return replace(
            self,
            fields=self.fields + (field,),
            has_edits=True,
        )
    
    def add_table(self, table: TableExtraction) -> "PageExtraction":
        """Add a new table extraction to this page."""
        # Check for duplicate table titles
        if self.get_table_by_title(table.title) is not None:
            raise ValueError(f"Table '{table.title}' already exists on page {self.page_number}")
        
        return replace(
            self,
            tables=self.tables + (table,),
            has_edits=True,
        )
    
    def remove_field(self, field_name: str) -> "PageExtraction":
        """Remove a field by name from this page."""
        updated_fields = [f for f in self.fields if f.field_name != field_name]
        
        if len(updated_fields) == len(self.fields):
            raise ValueError(f"Field '{field_name}' not found on page {self.page_number}")
        
        return replace(
            self,
            fields=tuple(updated_fields),
            has_edits=True,
        )
    
    def remove_table(self, table_title: str) -> "PageExtraction":
        """Remove a table by title from this page."""
        updated_tables = [t for t in self.tables if t.title != table_title]
        
        if len(updated_tables) == len(self.tables):
            raise ValueError(f"Table '{table_title}' not found on page {self.page_number}")
        
        return replace(
            self,
            tables=tuple(updated_tables),
            has_edits=True,
        )
    
    def mark_reviewed(self) -> "PageExtraction":
        """Mark this page as reviewed (even if no edits were made)."""
        return replace(self, has_edits=True)
    
    # ==================== Serialization ====================
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "page_number": self.page_number,
            "fields": [f.to_dict() for f in self.fields],
            "tables": [t.to_dict() for t in self.tables],
            "image_path": self.image_path,
            "has_edits": self.has_edits,
            "status": self.status,
            "markdown_text": self.markdown_text,
            "image_mime": self.image_mime,
            "rotation_applied": self.rotation_applied,
            "document_type_hint": self.document_type_hint,
            "document_type_confidence": self.document_type_confidence,
            "error_message": self.error_message,
            "total_extractions": self.total_extractions,
            "overall_confidence": self.overall_confidence.value,
            "low_confidence_count": self.low_confidence_count,
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"PageExtraction(page={self.page_number}, "
            f"fields={len(self.fields)}, "
            f"tables={len(self.tables)}, "
            f"confidence={self.overall_confidence.value:.2f})"
        )
