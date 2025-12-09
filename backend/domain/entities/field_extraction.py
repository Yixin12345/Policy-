"""
FieldExtraction Entity

Represents a single extracted field from a document (e.g., name, date, amount).
Rich domain entity with validation and business logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from ..value_objects.bounding_box import BoundingBox
from ..value_objects.confidence import Confidence


@dataclass
class FieldExtraction:
    """
    Domain entity representing an extracted field from a document.
    
    Encapsulates the field's identity, value, location, and metadata.
    Provides validation and business logic for field extraction data.
    """
    
    # Identity
    id: UUID = field(default_factory=uuid4)
    
    # Field information
    field_name: str = ""
    field_type: str = ""  # e.g., "text", "number", "date", "currency"
    value: str = ""
    normalized_value: Optional[Any] = None  # Parsed/normalized value
    
    # Quality metrics
    confidence: Confidence = field(default_factory=lambda: Confidence(0.0))
    
    # Location
    bounding_box: Optional[BoundingBox] = None
    page_number: int = 1
    
    # Metadata
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "unknown"  # e.g., "gpt4-vision", "tesseract", "azure-form-recognizer"
    was_edited: bool = False  # Tracks if field was user-edited after initial extraction
    
    def __post_init__(self):
        """Validate and normalize field data after initialization."""
        # Ensure UUID
        if not isinstance(self.id, UUID):
            if isinstance(self.id, str):
                try:
                    self.id = UUID(self.id)
                except ValueError:
                    # Legacy snapshots often store human-readable IDs; ensure we still
                    # produce a stable UUID rather than failing hydration.
                    self.id = uuid4()
            else:
                self.id = uuid4()
        
        # Normalize strings
        self.field_name = str(self.field_name).strip()
        self.field_type = str(self.field_type).strip().lower()
        self.value = str(self.value).strip()
        
        # Validate page number
        if self.page_number < 1:
            self.page_number = 1
        
        # Ensure Confidence is proper type
        if not isinstance(self.confidence, Confidence):
            if isinstance(self.confidence, (int, float)):
                self.confidence = Confidence(float(self.confidence))
            else:
                self.confidence = Confidence(0.0)
        
        # Ensure BoundingBox is proper type if provided
        if self.bounding_box is not None and not isinstance(self.bounding_box, BoundingBox):
            if isinstance(self.bounding_box, dict):
                self.bounding_box = BoundingBox.from_dict(self.bounding_box)
            else:
                self.bounding_box = None
    
    @classmethod
    def create(
        cls,
        field_name: str,
        value: str,
        field_type: str = "text",
        confidence: float = 0.0,
        bounding_box: Optional[BoundingBox] = None,
        page_number: int = 1,
        source: str = "unknown"
    ) -> FieldExtraction:
        """
        Factory method to create a FieldExtraction with validation.
        
        Args:
            field_name: Name of the field (e.g., "invoice_number")
            value: Extracted value as string
            field_type: Type of field (text, number, date, etc.)
            confidence: Confidence score (0-1)
            bounding_box: Optional location on page
            page_number: Page number (1-based)
            source: Extraction source/method
            
        Returns:
            New FieldExtraction instance
            
        Examples:
            >>> field = FieldExtraction.create(
            ...     field_name="invoice_number",
            ...     value="INV-12345",
            ...     confidence=0.95
            ... )
            >>> field.is_high_confidence()
            True
        """
        return cls(
            field_name=field_name,
            field_type=field_type,
            value=value,
            confidence=Confidence(confidence),
            bounding_box=bounding_box,
            page_number=page_number,
            source=source
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FieldExtraction:
        """
        Create FieldExtraction from dictionary representation.
        
        Args:
            data: Dictionary with field data
            
        Returns:
            New FieldExtraction instance
        """
        # Handle nested objects
        confidence_data = data.get('confidence', 0.0)
        if isinstance(confidence_data, dict):
            confidence = Confidence(confidence_data.get('value', 0.0))
        else:
            confidence = Confidence(confidence_data)
        
        bbox_data = data.get('bounding_box')
        bounding_box = BoundingBox.from_dict(bbox_data) if bbox_data else None
        
        # Handle datetime
        extracted_at = data.get('extracted_at')
        if isinstance(extracted_at, str):
            extracted_at = datetime.fromisoformat(extracted_at.replace('Z', '+00:00'))
        elif not isinstance(extracted_at, datetime):
            extracted_at = datetime.now(timezone.utc)
        
        return cls(
            id=data.get('id', uuid4()),
            field_name=data.get('field_name', ''),
            field_type=data.get('field_type', 'text'),
            value=data.get('value', ''),
            normalized_value=data.get('normalized_value'),
            confidence=confidence,
            bounding_box=bounding_box,
            page_number=data.get('page_number', 1),
            extracted_at=extracted_at,
            source=data.get('source', 'unknown'),
            was_edited=data.get('was_edited', False)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Returns:
            Dictionary with all field data
        """
        return {
            'id': str(self.id),
            'field_name': self.field_name,
            'field_type': self.field_type,
            'value': self.value,
            'normalized_value': self.normalized_value,
            'confidence': self.confidence.value,
            'bounding_box': self.bounding_box.to_dict() if self.bounding_box else None,
            'page_number': self.page_number,
            'extracted_at': self.extracted_at.isoformat(),
            'source': self.source,
            'was_edited': self.was_edited
        }
    
    def is_empty(self) -> bool:
        """Check if field has no value."""
        return len(self.value) == 0
    
    def has_value(self) -> bool:
        """Check if field has a value."""
        return len(self.value) > 0
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """
        Check if confidence exceeds threshold.
        
        Args:
            threshold: Minimum confidence level (default 0.8)
            
        Returns:
            True if confidence >= threshold
        """
        return self.confidence.value >= threshold
    
    def is_low_confidence(self, threshold: float = 0.5) -> bool:
        """
        Check if confidence is below threshold.
        
        Args:
            threshold: Maximum confidence level (default 0.5)
            
        Returns:
            True if confidence < threshold
        """
        return self.confidence.value < threshold
    
    def needs_review(self, confidence_threshold: float = 0.7) -> bool:
        """
        Check if field needs manual review.
        
        Args:
            confidence_threshold: Minimum acceptable confidence
            
        Returns:
            True if field should be reviewed (low confidence or empty)
        """
        return self.is_empty() or self.is_low_confidence(confidence_threshold)
    
    def has_location(self) -> bool:
        """Check if field has bounding box location."""
        return self.bounding_box is not None and self.bounding_box.is_valid()
    
    def update_value(self, new_value: str, new_confidence: Optional[float] = None) -> FieldExtraction:
        """
        Create updated field with new value.
        
        Args:
            new_value: New field value
            new_confidence: Optional new confidence score
            
        Returns:
            New FieldExtraction instance with updated value
            
        Examples:
            >>> field = FieldExtraction.create("name", "John", confidence=0.8)
            >>> updated = field.update_value("John Doe", 0.95)
            >>> updated.value
            'John Doe'
        """
        # Any invocation of update_value is considered an edit
        edited = True
        return FieldExtraction(
            id=self.id,
            field_name=self.field_name,
            field_type=self.field_type,
            value=new_value,
            normalized_value=self.normalized_value,
            confidence=Confidence(new_confidence) if new_confidence is not None else self.confidence,
            bounding_box=self.bounding_box,
            page_number=self.page_number,
            extracted_at=self.extracted_at,
            source=self.source,
            was_edited=edited or self.was_edited
        )
    
    def normalize_value(self, normalized: Any) -> FieldExtraction:
        """
        Create field with normalized value.
        
        Args:
            normalized: Parsed/normalized value
            
        Returns:
            New FieldExtraction instance with normalized value
            
        Examples:
            >>> field = FieldExtraction.create("amount", "$1,234.56")
            >>> normalized = field.normalize_value(1234.56)
            >>> normalized.normalized_value
            1234.56
        """
        return FieldExtraction(
            id=self.id,
            field_name=self.field_name,
            field_type=self.field_type,
            value=self.value,
            normalized_value=normalized,
            confidence=self.confidence,
            bounding_box=self.bounding_box,
            page_number=self.page_number,
            extracted_at=self.extracted_at,
            source=self.source
        )
    
    def __str__(self) -> str:
        """String representation."""
        conf_pct = int(self.confidence.value * 100)
        return f"Field({self.field_name}='{self.value}', conf={conf_pct}%)"
    
    def __repr__(self) -> str:
        """Developer representation."""
        return (
            f"FieldExtraction(id={self.id}, field_name='{self.field_name}', "
            f"value='{self.value}', confidence={self.confidence.value:.2f})"
        )
    
    def __eq__(self, other: object) -> bool:
        """Equality based on ID."""
        if not isinstance(other, FieldExtraction):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash based on ID."""
        return hash(self.id)
