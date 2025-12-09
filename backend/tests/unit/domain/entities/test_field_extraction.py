"""
Unit tests for FieldExtraction entity
"""
import pytest
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

# Add project root to Python path
project_root = Path(__file__).resolve().parents[5]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.value_objects.bounding_box import BoundingBox
from backend.domain.value_objects.confidence import Confidence


class TestFieldExtractionCreation:
    """Test FieldExtraction object creation."""
    
    def test_create_minimal(self):
        """Test creating field with minimal data."""
        field = FieldExtraction.create(
            field_name="invoice_number",
            value="INV-12345"
        )
        assert field.field_name == "invoice_number"
        assert field.value == "INV-12345"
        assert field.field_type == "text"
        assert isinstance(field.id, UUID)
        assert isinstance(field.confidence, Confidence)
        assert field.page_number == 1
    
    def test_create_with_confidence(self):
        """Test creating field with confidence."""
        field = FieldExtraction.create(
            field_name="amount",
            value="$1,234.56",
            confidence=0.95
        )
        assert field.confidence.value == 0.95
    
    def test_create_with_bounding_box(self):
        """Test creating field with location."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        field = FieldExtraction.create(
            field_name="name",
            value="John Doe",
            bounding_box=bbox
        )
        assert field.bounding_box == bbox
        assert field.has_location()
    
    def test_create_with_page_number(self):
        """Test creating field with page number."""
        field = FieldExtraction.create(
            field_name="total",
            value="100.00",
            page_number=3
        )
        assert field.page_number == 3
    
    def test_create_with_source(self):
        """Test creating field with source."""
        field = FieldExtraction.create(
            field_name="date",
            value="2024-01-15",
            source="gpt4-vision"
        )
        assert field.source == "gpt4-vision"


class TestFieldExtractionValidation:
    """Test FieldExtraction validation logic."""
    
    def test_normalizes_field_name(self):
        """Test field name is trimmed."""
        field = FieldExtraction.create(
            field_name="  invoice_number  ",
            value="INV-123"
        )
        assert field.field_name == "invoice_number"
    
    def test_normalizes_value(self):
        """Test value is trimmed."""
        field = FieldExtraction.create(
            field_name="name",
            value="  John Doe  "
        )
        assert field.value == "John Doe"
    
    def test_normalizes_field_type(self):
        """Test field type is lowercase and trimmed."""
        field = FieldExtraction.create(
            field_name="amount",
            value="100",
            field_type="  NUMBER  "
        )
        assert field.field_type == "number"
    
    def test_page_number_minimum_one(self):
        """Test page number cannot be less than 1."""
        field = FieldExtraction(
            field_name="test",
            value="test",
            page_number=-5
        )
        assert field.page_number == 1
    
    def test_converts_confidence_from_float(self):
        """Test confidence float is converted to Confidence object."""
        field = FieldExtraction(
            field_name="test",
            value="test",
            confidence=0.85
        )
        assert isinstance(field.confidence, Confidence)
        assert field.confidence.value == 0.85


class TestFieldExtractionFromDict:
    """Test FieldExtraction.from_dict() factory method."""
    
    def test_from_dict_basic(self):
        """Test creating from basic dictionary."""
        data = {
            'field_name': 'invoice_number',
            'value': 'INV-12345',
            'confidence': 0.95
        }
        field = FieldExtraction.from_dict(data)
        assert field.field_name == 'invoice_number'
        assert field.value == 'INV-12345'
        assert field.confidence.value == 0.95
    
    def test_from_dict_with_bbox(self):
        """Test creating from dict with bounding box."""
        data = {
            'field_name': 'name',
            'value': 'John Doe',
            'bounding_box': {'x': 0.1, 'y': 0.2, 'width': 0.3, 'height': 0.4}
        }
        field = FieldExtraction.from_dict(data)
        assert field.bounding_box is not None
        assert field.bounding_box.x == 0.1
    
    def test_from_dict_with_nested_confidence(self):
        """Test creating from dict with nested confidence object."""
        data = {
            'field_name': 'amount',
            'value': '100',
            'confidence': {'value': 0.88}
        }
        field = FieldExtraction.from_dict(data)
        assert field.confidence.value == 0.88
    
    def test_from_dict_with_id(self):
        """Test creating from dict preserves ID."""
        test_id = uuid4()
        data = {
            'id': test_id,
            'field_name': 'test',
            'value': 'test'
        }
        field = FieldExtraction.from_dict(data)
        assert field.id == test_id


class TestFieldExtractionToDict:
    """Test FieldExtraction.to_dict() method."""
    
    def test_to_dict_basic(self):
        """Test converting to dictionary."""
        field = FieldExtraction.create(
            field_name="invoice_number",
            value="INV-12345",
            confidence=0.95
        )
        data = field.to_dict()
        
        assert data['field_name'] == 'invoice_number'
        assert data['value'] == 'INV-12345'
        assert data['confidence'] == 0.95
        assert 'id' in data
        assert isinstance(data['id'], str)
    
    def test_to_dict_with_bbox(self):
        """Test dictionary includes bounding box."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        field = FieldExtraction.create(
            field_name="name",
            value="John",
            bounding_box=bbox
        )
        data = field.to_dict()
        
        assert data['bounding_box'] is not None
        assert data['bounding_box']['x'] == 0.1
    
    def test_to_dict_roundtrip(self):
        """Test to_dict -> from_dict roundtrip."""
        original = FieldExtraction.create(
            field_name="test",
            value="value",
            confidence=0.75,
            page_number=2,
            source="test-source"
        )
        data = original.to_dict()
        restored = FieldExtraction.from_dict(data)
        
        assert restored.field_name == original.field_name
        assert restored.value == original.value
        assert restored.confidence.value == original.confidence.value
        assert restored.page_number == original.page_number
        assert restored.source == original.source


class TestFieldExtractionQueries:
    """Test FieldExtraction query methods."""
    
    def test_is_empty_true(self):
        """Test is_empty for empty field."""
        field = FieldExtraction.create(field_name="test", value="")
        assert field.is_empty()
    
    def test_is_empty_false(self):
        """Test is_empty for field with value."""
        field = FieldExtraction.create(field_name="test", value="something")
        assert not field.is_empty()
    
    def test_has_value_true(self):
        """Test has_value for field with value."""
        field = FieldExtraction.create(field_name="test", value="something")
        assert field.has_value()
    
    def test_has_value_false(self):
        """Test has_value for empty field."""
        field = FieldExtraction.create(field_name="test", value="")
        assert not field.has_value()
    
    def test_is_high_confidence_true(self):
        """Test is_high_confidence for high confidence field."""
        field = FieldExtraction.create(
            field_name="test",
            value="test",
            confidence=0.95
        )
        assert field.is_high_confidence(threshold=0.8)
    
    def test_is_high_confidence_false(self):
        """Test is_high_confidence for low confidence field."""
        field = FieldExtraction.create(
            field_name="test",
            value="test",
            confidence=0.6
        )
        assert not field.is_high_confidence(threshold=0.8)
    
    def test_is_low_confidence_true(self):
        """Test is_low_confidence for low confidence field."""
        field = FieldExtraction.create(
            field_name="test",
            value="test",
            confidence=0.3
        )
        assert field.is_low_confidence(threshold=0.5)
    
    def test_is_low_confidence_false(self):
        """Test is_low_confidence for high confidence field."""
        field = FieldExtraction.create(
            field_name="test",
            value="test",
            confidence=0.8
        )
        assert not field.is_low_confidence(threshold=0.5)
    
    def test_needs_review_empty(self):
        """Test needs_review for empty field."""
        field = FieldExtraction.create(
            field_name="test",
            value="",
            confidence=0.9
        )
        assert field.needs_review()
    
    def test_needs_review_low_confidence(self):
        """Test needs_review for low confidence field."""
        field = FieldExtraction.create(
            field_name="test",
            value="something",
            confidence=0.5
        )
        assert field.needs_review(confidence_threshold=0.7)
    
    def test_needs_review_false(self):
        """Test needs_review false for good field."""
        field = FieldExtraction.create(
            field_name="test",
            value="something",
            confidence=0.9
        )
        assert not field.needs_review(confidence_threshold=0.7)
    
    def test_has_location_true(self):
        """Test has_location for field with valid bbox."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        field = FieldExtraction.create(
            field_name="test",
            value="test",
            bounding_box=bbox
        )
        assert field.has_location()
    
    def test_has_location_false_no_bbox(self):
        """Test has_location false when no bbox."""
        field = FieldExtraction.create(field_name="test", value="test")
        assert not field.has_location()
    
    def test_has_location_false_invalid_bbox(self):
        """Test has_location false for invalid bbox."""
        bbox = BoundingBox(0.0, 0.0, 0.0, 0.0)  # Empty bbox
        field = FieldExtraction.create(
            field_name="test",
            value="test",
            bounding_box=bbox
        )
        assert not field.has_location()


class TestFieldExtractionMutations:
    """Test FieldExtraction mutation methods (return new instances)."""
    
    def test_update_value(self):
        """Test updating value creates new instance."""
        original = FieldExtraction.create(
            field_name="name",
            value="John",
            confidence=0.8
        )
        updated = original.update_value("John Doe", 0.95)
        
        # New instance with updated value
        assert updated.value == "John Doe"
        assert updated.confidence.value == 0.95
        
        # Original unchanged
        assert original.value == "John"
        assert original.confidence.value == 0.8
        
        # Same ID
        assert updated.id == original.id
    
    def test_update_value_preserves_confidence(self):
        """Test update_value preserves confidence if not provided."""
        original = FieldExtraction.create(
            field_name="name",
            value="John",
            confidence=0.8
        )
        updated = original.update_value("Jane")
        
        assert updated.value == "Jane"
        assert updated.confidence.value == 0.8
    
    def test_normalize_value(self):
        """Test normalizing value creates new instance."""
        original = FieldExtraction.create(
            field_name="amount",
            value="$1,234.56",
            field_type="currency"
        )
        normalized = original.normalize_value(1234.56)
        
        # New instance with normalized value
        assert normalized.value == "$1,234.56"  # Original string preserved
        assert normalized.normalized_value == 1234.56
        
        # Original unchanged
        assert original.normalized_value is None
        
        # Same ID
        assert normalized.id == original.id


class TestFieldExtractionStringRepresentation:
    """Test string representations."""
    
    def test_str_representation(self):
        """Test __str__ representation."""
        field = FieldExtraction.create(
            field_name="invoice_number",
            value="INV-12345",
            confidence=0.95
        )
        result = str(field)
        assert "invoice_number" in result
        assert "INV-12345" in result
        assert "95%" in result
    
    def test_repr_representation(self):
        """Test __repr__ representation."""
        field = FieldExtraction.create(
            field_name="name",
            value="John",
            confidence=0.8
        )
        result = repr(field)
        assert "FieldExtraction" in result
        assert "name" in result
        assert "John" in result


class TestFieldExtractionEquality:
    """Test equality and hashing."""
    
    def test_equality_same_id(self):
        """Test equality based on ID."""
        field_id = uuid4()
        field1 = FieldExtraction(id=field_id, field_name="test", value="val1")
        field2 = FieldExtraction(id=field_id, field_name="test", value="val2")
        
        assert field1 == field2  # Same ID
    
    def test_equality_different_id(self):
        """Test inequality for different IDs."""
        field1 = FieldExtraction.create(field_name="test", value="val")
        field2 = FieldExtraction.create(field_name="test", value="val")
        
        assert field1 != field2  # Different IDs
    
    def test_hash_consistency(self):
        """Test hash is based on ID."""
        field_id = uuid4()
        field1 = FieldExtraction(id=field_id, field_name="test", value="val1")
        field2 = FieldExtraction(id=field_id, field_name="test", value="val2")
        
        assert hash(field1) == hash(field2)
    
    def test_can_use_in_set(self):
        """Test fields can be used in sets."""
        field1 = FieldExtraction.create(field_name="test1", value="val")
        field2 = FieldExtraction.create(field_name="test2", value="val")
        field_set = {field1, field2}
        
        assert len(field_set) == 2
        assert field1 in field_set
        assert field2 in field_set
