"""
Unit tests for PageExtraction entity.
"""

import pytest
from uuid import uuid4

from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.entities.table_extraction import TableExtraction, TableCell
from backend.domain.value_objects.bounding_box import BoundingBox
from backend.domain.value_objects.confidence import Confidence


@pytest.fixture
def sample_field():
    """Sample field extraction."""
    return FieldExtraction.create(
        field_name="invoice_number",
        value="INV-001",
        confidence=0.95,
    )


@pytest.fixture
def sample_field_low_conf():
    """Sample low-confidence field."""
    return FieldExtraction.create(
        field_name="total_amount",
        value="$1,234.56",
        confidence=0.35,
    )


@pytest.fixture
def sample_table():
    """Sample table extraction."""
    cells = [
        TableCell(row=0, column=0, content="Product", confidence=Confidence(0.98)),
        TableCell(row=0, column=1, content="Price", confidence=Confidence(0.98)),
        TableCell(row=1, column=0, content="Widget", confidence=Confidence(0.95)),
        TableCell(row=1, column=1, content="$10.00", confidence=Confidence(0.92)),
    ]
    return TableExtraction(
        id=uuid4(),
        cells=cells,
        page_number=1,
        confidence=Confidence(0.95),
        title="LineItems",
    )


@pytest.fixture
def sample_table_low_conf():
    """Sample table with low confidence cells."""
    cells = [
        TableCell(row=0, column=0, content="Name", confidence=Confidence(0.98)),
        TableCell(row=1, column=0, content="John", confidence=Confidence(0.25)),  # Low
    ]
    return TableExtraction(
        id=uuid4(),
        cells=cells,
        page_number=1,
        confidence=Confidence(0.4),  # Low overall confidence
        title="CustomerInfo",
    )


# ==================== Initialization Tests ====================

def test_page_extraction_creation():
    """Test basic page extraction creation."""
    page = PageExtraction.create(page_number=1)
    
    assert page.page_number == 1
    assert len(page.fields) == 0
    assert len(page.tables) == 0
    assert page.is_empty
    assert not page.has_edits


def test_page_extraction_with_data(sample_field, sample_table):
    """Test page extraction with fields and tables."""
    page = PageExtraction.create(
        page_number=2,
        fields=[sample_field],
        tables=[sample_table],
        image_path="/path/to/page2.png",
    )
    
    assert page.page_number == 2
    assert len(page.fields) == 1
    assert len(page.tables) == 1
    assert page.total_extractions == 2
    assert page.image_path == "/path/to/page2.png"
    assert not page.is_empty


def test_page_number_validation():
    """Test page number must be >= 1."""
    with pytest.raises(ValueError, match="Page number must be >= 1"):
        PageExtraction.create(page_number=0)
    
    with pytest.raises(ValueError, match="Page number must be >= 1"):
        PageExtraction.create(page_number=-1)


def test_immutability():
    """Test PageExtraction is immutable."""
    page = PageExtraction.create(page_number=1)
    
    with pytest.raises(Exception):  # FrozenInstanceError
        page.page_number = 2


# ==================== Query Methods Tests ====================

def test_total_extractions(sample_field, sample_table):
    """Test total extraction count."""
    page = PageExtraction.create(
        page_number=1,
        fields=[sample_field, sample_field],
        tables=[sample_table],
    )
    
    assert page.total_extractions == 3


def test_has_fields():
    """Test has_fields property."""
    page = PageExtraction.create(page_number=1)
    assert not page.has_fields
    
    field = FieldExtraction.create("test", "value", confidence=0.9)
    page = PageExtraction.create(page_number=1, fields=[field])
    assert page.has_fields


def test_has_tables(sample_table):
    """Test has_tables property."""
    page = PageExtraction.create(page_number=1)
    assert not page.has_tables
    
    page = PageExtraction.create(page_number=1, tables=[sample_table])
    assert page.has_tables


def test_is_empty():
    """Test is_empty property."""
    page = PageExtraction.create(page_number=1)
    assert page.is_empty
    
    field = FieldExtraction.create("test", "value", confidence=0.9)
    page = PageExtraction.create(page_number=1, fields=[field])
    assert not page.is_empty


def test_overall_confidence_empty_page():
    """Test overall confidence for empty page is 1.0."""
    page = PageExtraction.create(page_number=1)
    assert page.overall_confidence.value == 1.0


def test_overall_confidence_with_fields(sample_field, sample_field_low_conf):
    """Test overall confidence calculation with fields."""
    page = PageExtraction.create(
        page_number=1,
        fields=[sample_field, sample_field_low_conf],
    )
    
    # (0.95 + 0.35) / 2 = 0.65
    assert abs(page.overall_confidence.value - 0.65) < 0.01


def test_overall_confidence_with_tables(sample_table, sample_table_low_conf):
    """Test overall confidence calculation with tables."""
    page = PageExtraction.create(
        page_number=1,
        tables=[sample_table, sample_table_low_conf],
    )
    
    # Should average the confidence of both tables
    avg = (sample_table.confidence.value + sample_table_low_conf.confidence.value) / 2
    assert abs(page.overall_confidence.value - avg) < 0.01


def test_overall_confidence_mixed(sample_field, sample_table):
    """Test overall confidence with both fields and tables."""
    page = PageExtraction.create(
        page_number=1,
        fields=[sample_field],
        tables=[sample_table],
    )
    
    # Should average field confidence and table confidence
    avg = (sample_field.confidence.value + sample_table.confidence.value) / 2
    assert abs(page.overall_confidence.value - avg) < 0.01


def test_get_field_by_name(sample_field):
    """Test finding field by name."""
    page = PageExtraction.create(page_number=1, fields=[sample_field])
    
    found = page.get_field_by_name("invoice_number")
    assert found is not None
    assert found.field_name == "invoice_number"
    
    not_found = page.get_field_by_name("nonexistent")
    assert not_found is None


def test_get_table_by_title(sample_table):
    """Test finding table by title."""
    page = PageExtraction.create(page_number=1, tables=[sample_table])
    
    found = page.get_table_by_title("LineItems")
    assert found is not None
    assert found.title == "LineItems"
    
    not_found = page.get_table_by_title("NonExistent")
    assert not_found is None


def test_low_confidence_count(sample_field, sample_field_low_conf, sample_table_low_conf):
    """Test counting low confidence extractions."""
    page = PageExtraction.create(
        page_number=1,
        fields=[sample_field, sample_field_low_conf],
        tables=[sample_table_low_conf],
    )
    
    # 1 low-conf field + 1 table with low-conf cells = 2
    assert page.low_confidence_count == 2


def test_has_low_confidence_items(sample_field, sample_field_low_conf):
    """Test checking for low confidence items."""
    # No low confidence
    page = PageExtraction.create(page_number=1, fields=[sample_field])
    assert not page.has_low_confidence_items()
    
    # Has low confidence
    page = PageExtraction.create(page_number=1, fields=[sample_field_low_conf])
    assert page.has_low_confidence_items()


def test_needs_review(sample_field_low_conf):
    """Test needs_review logic."""
    # Low confidence, not edited -> needs review
    page = PageExtraction.create(page_number=1, fields=[sample_field_low_conf])
    assert page.needs_review()
    
    # Low confidence, but edited -> doesn't need review
    page = page.mark_reviewed()
    assert not page.needs_review()
    
    # High confidence -> doesn't need review
    field = FieldExtraction.create("test", "value", confidence=0.95)
    page = PageExtraction.create(page_number=1, fields=[field])
    assert not page.needs_review()


# ==================== Mutation Methods Tests ====================

def test_update_field(sample_field):
    """Test updating an existing field."""
    page = PageExtraction.create(page_number=1, fields=[sample_field])
    
    updated_field = sample_field.update_value("INV-002")
    new_page = page.update_field("invoice_number", updated_field)
    
    assert new_page.get_field_by_name("invoice_number").value == "INV-002"
    assert new_page.has_edits
    
    # Original page is unchanged
    assert page.get_field_by_name("invoice_number").value == "INV-001"
    assert not page.has_edits


def test_update_field_not_found():
    """Test updating non-existent field raises error."""
    page = PageExtraction.create(page_number=1)
    field = FieldExtraction.create("test", "value", Confidence(0.9))
    
    with pytest.raises(ValueError, match="Field 'test' not found"):
        page.update_field("test", field)


def test_update_table(sample_table):
    """Test updating an existing table."""
    page = PageExtraction.create(page_number=1, tables=[sample_table])
    
    new_cell = TableCell(row=2, column=0, content="NewRow", confidence=Confidence(0.9))
    updated_table = sample_table.add_cell(new_cell)
    new_page = page.update_table("LineItems", updated_table)
    
    assert len(new_page.get_table_by_title("LineItems").cells) == 5
    assert new_page.has_edits
    
    # Original unchanged
    assert len(page.get_table_by_title("LineItems").cells) == 4


def test_update_table_not_found():
    """Test updating non-existent table raises error."""
    page = PageExtraction.create(page_number=1)
    table = TableExtraction(
        id=uuid4(),
        cells=[],
        page_number=1,
        confidence=Confidence(0.9),
        title="Test",
    )
    
    with pytest.raises(ValueError, match="Table 'Test' not found"):
        page.update_table("Test", table)


def test_add_field():
    """Test adding a new field."""
    page = PageExtraction.create(page_number=1)
    field = FieldExtraction.create("new_field", "value", confidence=0.9)
    
    new_page = page.add_field(field)
    
    assert len(new_page.fields) == 1
    assert new_page.get_field_by_name("new_field") is not None
    assert new_page.has_edits


def test_add_duplicate_field(sample_field):
    """Test adding duplicate field raises error."""
    page = PageExtraction.create(page_number=1, fields=[sample_field])
    
    duplicate = FieldExtraction.create("invoice_number", "other", confidence=0.9)
    
    with pytest.raises(ValueError, match="Field 'invoice_number' already exists"):
        page.add_field(duplicate)


def test_add_table():
    """Test adding a new table."""
    page = PageExtraction.create(page_number=1)
    table = TableExtraction(
        id=uuid4(),
        cells=[],
        page_number=1,
        confidence=Confidence(0.9),
        title="NewTable",
    )
    
    new_page = page.add_table(table)
    
    assert len(new_page.tables) == 1
    assert new_page.get_table_by_title("NewTable") is not None
    assert new_page.has_edits


def test_add_duplicate_table(sample_table):
    """Test adding duplicate table raises error."""
    page = PageExtraction.create(page_number=1, tables=[sample_table])
    
    duplicate = TableExtraction(
        id=uuid4(),
        cells=[],
        page_number=1,
        confidence=Confidence(0.9),
        title="LineItems",
    )
    
    with pytest.raises(ValueError, match="Table 'LineItems' already exists"):
        page.add_table(duplicate)


def test_remove_field(sample_field):
    """Test removing a field."""
    field2 = FieldExtraction.create("other", "value", confidence=0.9)
    page = PageExtraction.create(page_number=1, fields=[sample_field, field2])
    
    new_page = page.remove_field("invoice_number")
    
    assert len(new_page.fields) == 1
    assert new_page.get_field_by_name("invoice_number") is None
    assert new_page.get_field_by_name("other") is not None
    assert new_page.has_edits


def test_remove_field_not_found():
    """Test removing non-existent field raises error."""
    page = PageExtraction.create(page_number=1)
    
    with pytest.raises(ValueError, match="Field 'nonexistent' not found"):
        page.remove_field("nonexistent")


def test_remove_table(sample_table):
    """Test removing a table."""
    table2 = TableExtraction(
        id=uuid4(),
        cells=[],
        page_number=1,
        confidence=Confidence(0.9),
        title="Other",
    )
    page = PageExtraction.create(page_number=1, tables=[sample_table, table2])
    
    new_page = page.remove_table("LineItems")
    
    assert len(new_page.tables) == 1
    assert new_page.get_table_by_title("LineItems") is None
    assert new_page.get_table_by_title("Other") is not None
    assert new_page.has_edits


def test_remove_table_not_found():
    """Test removing non-existent table raises error."""
    page = PageExtraction.create(page_number=1)
    
    with pytest.raises(ValueError, match="Table 'NonExistent' not found"):
        page.remove_table("NonExistent")


def test_mark_reviewed():
    """Test marking page as reviewed."""
    page = PageExtraction.create(page_number=1)
    assert not page.has_edits
    
    reviewed = page.mark_reviewed()
    assert reviewed.has_edits


# ==================== Serialization Tests ====================

def test_to_dict(sample_field, sample_table):
    """Test conversion to dictionary."""
    page = PageExtraction.create(
        page_number=3,
        fields=[sample_field],
        tables=[sample_table],
        image_path="/path/to/image.png",
    )
    
    data = page.to_dict()
    
    assert data["page_number"] == 3
    assert len(data["fields"]) == 1
    assert len(data["tables"]) == 1
    assert data["image_path"] == "/path/to/image.png"
    assert data["has_edits"] is False
    assert data["total_extractions"] == 2
    assert "overall_confidence" in data
    assert "low_confidence_count" in data


def test_from_dict(sample_field, sample_table):
    """Test creation from dictionary."""
    page = PageExtraction.create(
        page_number=3,
        fields=[sample_field],
        tables=[sample_table],
        image_path="/path/to/image.png",
    )
    
    data = page.to_dict()
    restored = PageExtraction.from_dict(data)
    
    assert restored.page_number == page.page_number
    assert len(restored.fields) == len(page.fields)
    assert len(restored.tables) == len(page.tables)
    assert restored.image_path == page.image_path


def test_serialization_roundtrip(sample_field, sample_table):
    """Test serialization and deserialization preserve data."""
    original = PageExtraction.create(
        page_number=5,
        fields=[sample_field],
        tables=[sample_table],
        image_path="/path/to/image.png",
    )
    
    data = original.to_dict()
    restored = PageExtraction.from_dict(data)
    
    assert restored.page_number == original.page_number
    assert len(restored.fields) == len(original.fields)
    assert restored.fields[0].field_name == original.fields[0].field_name
    assert len(restored.tables) == len(original.tables)
    assert restored.tables[0].title == original.tables[0].title


# ==================== String Representation Tests ====================

def test_repr():
    """Test string representation."""
    page = PageExtraction.create(page_number=7)
    
    repr_str = repr(page)
    assert "page=7" in repr_str
    assert "fields=0" in repr_str
    assert "tables=0" in repr_str
    assert "confidence=" in repr_str
