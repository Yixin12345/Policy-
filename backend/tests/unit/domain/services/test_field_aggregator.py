"""
Unit tests for FieldAggregator domain service.

Tests field aggregation business logic without any dependencies on legacy code.
"""
import pytest
from backend.domain.services.field_aggregator import (
    FieldAggregator, 
    FieldAggregation, 
    DocumentFieldSummary
)
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.page_extraction import PageExtraction


@pytest.fixture
def aggregator():
    """Create a FieldAggregator with default threshold."""
    return FieldAggregator(low_confidence_threshold=0.4)


@pytest.fixture
def sample_fields_page1():
    """Create sample fields for page 1."""
    return [
        FieldExtraction.create(
            field_name="invoice_number",
            value="INV-001",
            field_type="text",
            confidence=0.9
        ),
        FieldExtraction.create(
            field_name="total_amount",
            value="$1,500.00",
            field_type="currency",
            confidence=0.8
        ),
        FieldExtraction.create(
            field_name="date",
            value="2024-01-15",
            field_type="date",
            confidence=0.3  # Low confidence
        )
    ]


@pytest.fixture
def sample_fields_page2():
    """Create sample fields for page 2."""
    return [
        FieldExtraction.create(
            field_name="invoice_number",
            value="INV-001",  # Same value - consistent
            field_type="text", 
            confidence=0.95
        ),
        FieldExtraction.create(
            field_name="total_amount",
            value="$1,500.00",  # Same value - consistent
            field_type="currency",
            confidence=0.85
        ),
        FieldExtraction.create(
            field_name="vendor_name",
            value="ABC Corp",
            field_type="text",
            confidence=0.7
        ),
        FieldExtraction.create(
            field_name="inconsistent_field",
            value="Value A",
            field_type="text",
            confidence=0.6
        )
    ]


@pytest.fixture  
def sample_fields_page3():
    """Create sample fields for page 3."""
    return [
        FieldExtraction.create(
            field_name="vendor_name",
            value="ABC Corp",  # Same as page 2
            field_type="text",
            confidence=0.8
        ),
        FieldExtraction.create(
            field_name="inconsistent_field",
            value="Value B",  # Different from page 2 - inconsistent
            field_type="text", 
            confidence=0.7
        )
    ]


@pytest.fixture
def sample_pages(sample_fields_page1, sample_fields_page2, sample_fields_page3):
    """Create sample pages for testing."""
    return [
        PageExtraction.create(page_number=1, fields=sample_fields_page1, tables=[]),
        PageExtraction.create(page_number=2, fields=sample_fields_page2, tables=[]),
        PageExtraction.create(page_number=3, fields=sample_fields_page3, tables=[])
    ]


class TestFieldAggregatorInitialization:
    """Test FieldAggregator initialization."""
    
    def test_default_initialization(self):
        """Test initialization with default threshold."""
        aggregator = FieldAggregator(low_confidence_threshold=0.4)
        assert aggregator.low_confidence_threshold == 0.4
    
    def test_custom_threshold(self):
        """Test initialization with custom threshold."""
        aggregator = FieldAggregator(low_confidence_threshold=0.3)
        assert aggregator.low_confidence_threshold == 0.3
    
    def test_invalid_threshold_low(self):
        """Test initialization with invalid low threshold."""
        with pytest.raises(ValueError, match="low_confidence_threshold must be between 0.0 and 1.0"):
            FieldAggregator(low_confidence_threshold=-0.1)
    
    def test_invalid_threshold_high(self):
        """Test initialization with invalid high threshold."""
        with pytest.raises(ValueError, match="low_confidence_threshold must be between 0.0 and 1.0"):
            FieldAggregator(low_confidence_threshold=1.1)


class TestAggregateFieldsByName:
    """Test field aggregation by name."""
    
    def test_aggregate_empty_pages(self, aggregator):
        """Test aggregation with empty pages."""
        result = aggregator.aggregate_fields_by_name([])
        assert result == {}
    
    def test_aggregate_fields_by_name(self, aggregator, sample_pages):
        """Test aggregation by field name."""
        result = aggregator.aggregate_fields_by_name(sample_pages)
        
        # Should have 5 unique field names
        assert len(result) == 5
        assert "invoice_number" in result
        assert "total_amount" in result
        assert "date" in result
        assert "vendor_name" in result
        assert "inconsistent_field" in result
        
        # Check invoice_number aggregation (appears on pages 1 and 2)
        invoice_agg = result["invoice_number"]
        assert invoice_agg.field_name == "invoice_number"
        assert invoice_agg.field_type == "text"
        assert invoice_agg.total_occurrences == 2
        assert invoice_agg.pages_found == {1, 2}
        assert invoice_agg.values == ["INV-001"]  # Consistent value
        assert invoice_agg.is_consistent is True
        assert invoice_agg.most_common_value == "INV-001"
        # Average confidence: (0.9 + 0.95) / 2 = 0.925
        assert abs(invoice_agg.average_confidence - 0.925) < 0.001
        
        # Check inconsistent_field (appears on pages 2 and 3 with different values)
        inconsistent_agg = result["inconsistent_field"]
        assert inconsistent_agg.field_name == "inconsistent_field"
        assert inconsistent_agg.total_occurrences == 2
        assert inconsistent_agg.pages_found == {2, 3}
        assert set(inconsistent_agg.values) == {"Value A", "Value B"}
        assert inconsistent_agg.is_consistent is False
        
        # Check date (appears only on page 1)
        date_agg = result["date"]
        assert date_agg.field_name == "date"
        assert date_agg.total_occurrences == 1
        assert date_agg.pages_found == {1}
        assert date_agg.is_consistent is True
        assert date_agg.average_confidence == 0.3


class TestAggregateFieldsByType:
    """Test field aggregation by type."""
    
    def test_aggregate_empty_pages(self, aggregator):
        """Test aggregation with empty pages."""
        result = aggregator.aggregate_fields_by_type([])
        assert result == {}
    
    def test_aggregate_fields_by_type(self, aggregator, sample_pages):
        """Test aggregation by field type."""
        result = aggregator.aggregate_fields_by_type(sample_pages)
        
        # Should have 3 unique field types
        assert len(result) == 3
        assert "text" in result
        assert "currency" in result
        assert "date" in result
        
        # Check text type aggregation (includes invoice_number, vendor_name, inconsistent_field)
        text_agg = result["text"]
        assert text_agg.field_name == "text"  # Uses type as name
        assert text_agg.field_type == "text"
        assert text_agg.total_occurrences == 6  # invoice_number(2) + vendor_name(2) + inconsistent_field(2)
        assert text_agg.pages_found == {1, 2, 3}
        assert not text_agg.is_consistent  # Mixed values
        
        # Check currency type (only total_amount)
        currency_agg = result["currency"]
        assert currency_agg.field_name == "currency"
        assert currency_agg.field_type == "currency"
        assert currency_agg.total_occurrences == 2
        assert currency_agg.pages_found == {1, 2}
        assert currency_agg.values == ["$1,500.00"]
        assert currency_agg.is_consistent is True
        
        # Check date type (only date field)
        date_agg = result["date"]
        assert date_agg.field_name == "date"
        assert date_agg.field_type == "date"
        assert date_agg.total_occurrences == 1
        assert date_agg.pages_found == {1}
        assert date_agg.is_consistent is True


class TestCreateDocumentSummary:
    """Test document summary creation."""
    
    def test_create_empty_document_summary(self, aggregator):
        """Test summary creation with empty pages."""
        summary = aggregator.create_document_summary([])
        
        assert summary.total_fields == 0
        assert summary.unique_field_names == set()
        assert summary.total_pages == 0
        assert summary.field_aggregations == []
        assert summary.overall_confidence == 0.0
        assert summary.fields_needing_review == 0
    
    def test_create_document_summary(self, aggregator, sample_pages):
        """Test comprehensive document summary creation."""
        summary = aggregator.create_document_summary(sample_pages)
        
        # Basic counts
        assert summary.total_fields == 9  # Total field instances across all pages
        assert summary.unique_field_names == {
            "invoice_number", "total_amount", "date", "vendor_name", "inconsistent_field"
        }
        assert summary.total_pages == 3
        
        # Check field aggregations
        assert len(summary.field_aggregations) == 5
        agg_names = {agg.field_name for agg in summary.field_aggregations}
        assert agg_names == {"invoice_number", "total_amount", "date", "vendor_name", "inconsistent_field"}
        
        # Check overall confidence calculation
        # All confidences: 0.9, 0.8, 0.3, 0.95, 0.85, 0.7, 0.6, 0.8, 0.7
        # Sum: 6.65, Count: 9, Average: ~0.739
        expected_confidence = (0.9 + 0.8 + 0.3 + 0.95 + 0.85 + 0.7 + 0.6 + 0.8 + 0.7) / 9
        assert abs(summary.overall_confidence - expected_confidence) < 0.001
        
        # Check fields needing review (confidence <= 0.4)
        assert summary.fields_needing_review == 1  # Only the date field with 0.3 confidence


class TestFindInconsistentFields:
    """Test finding inconsistent fields."""
    
    def test_find_inconsistent_fields_empty(self, aggregator):
        """Test finding inconsistent fields with empty pages."""
        result = aggregator.find_inconsistent_fields([])
        assert result == []
    
    def test_find_inconsistent_fields(self, aggregator, sample_pages):
        """Test finding fields with inconsistent values."""
        result = aggregator.find_inconsistent_fields(sample_pages)
        
        # Only inconsistent_field should be inconsistent
        assert len(result) == 1
        inconsistent = result[0]
        assert inconsistent.field_name == "inconsistent_field"
        assert inconsistent.is_consistent is False
        assert set(inconsistent.values) == {"Value A", "Value B"}


class TestFindFieldsAcrossPages:
    """Test finding specific fields across pages."""
    
    def test_find_fields_across_pages_empty(self, aggregator):
        """Test finding fields in empty pages."""
        result = aggregator.find_fields_across_pages([], "invoice_number")
        assert result == []
    
    def test_find_fields_across_pages(self, aggregator, sample_pages):
        """Test finding specific field across pages."""
        # Find invoice_number (appears on pages 1 and 2)
        result = aggregator.find_fields_across_pages(sample_pages, "invoice_number")
        
        assert len(result) == 2
        page_numbers = [page_num for page_num, _ in result]
        assert set(page_numbers) == {1, 2}
        
        # Check field values
        for page_num, field in result:
            assert field.field_name == "invoice_number"
            assert field.value == "INV-001"
    
    def test_find_nonexistent_field(self, aggregator, sample_pages):
        """Test finding field that doesn't exist."""
        result = aggregator.find_fields_across_pages(sample_pages, "nonexistent_field")
        assert result == []


class TestCalculateFieldCoverage:
    """Test field coverage calculation."""
    
    def test_calculate_coverage_empty(self, aggregator):
        """Test coverage calculation with empty pages."""
        result = aggregator.calculate_field_coverage([])
        assert result == {}
    
    def test_calculate_field_coverage(self, aggregator, sample_pages):
        """Test field coverage across pages."""
        result = aggregator.calculate_field_coverage(sample_pages)
        
        # invoice_number: appears on pages 1,2 out of 3 = 2/3 = 0.667
        assert abs(result["invoice_number"] - 2/3) < 0.001
        
        # total_amount: appears on pages 1,2 out of 3 = 2/3 = 0.667  
        assert abs(result["total_amount"] - 2/3) < 0.001
        
        # date: appears on page 1 out of 3 = 1/3 = 0.333
        assert abs(result["date"] - 1/3) < 0.001
        
        # vendor_name: appears on pages 2,3 out of 3 = 2/3 = 0.667
        assert abs(result["vendor_name"] - 2/3) < 0.001
        
        # inconsistent_field: appears on pages 2,3 out of 3 = 2/3 = 0.667
        assert abs(result["inconsistent_field"] - 2/3) < 0.001


class TestFieldAggregation:
    """Test FieldAggregation value object."""
    
    def test_valid_aggregation_creation(self):
        """Test creating valid FieldAggregation."""
        agg = FieldAggregation(
            field_name="test_field",
            field_type="text",
            total_occurrences=3,
            pages_found={1, 2, 3},
            values=["value1", "value2"],
            confidence_scores=[0.8, 0.9, 0.7],
            average_confidence=0.8,
            most_common_value="value1",
            is_consistent=False
        )
        
        assert agg.field_name == "test_field"
        assert agg.total_occurrences == 3
        assert agg.pages_found == {1, 2, 3}
        assert not agg.is_consistent
    
    def test_invalid_occurrence_count_mismatch(self):
        """Test validation fails when occurrence count doesn't match confidence scores."""
        with pytest.raises(ValueError, match="total_occurrences must equal length of confidence_scores"):
            FieldAggregation(
                field_name="test",
                field_type="text",
                total_occurrences=2,  # Mismatch
                pages_found={1},
                values=["value"],
                confidence_scores=[0.8, 0.9, 0.7],  # 3 scores
                average_confidence=0.8,
                most_common_value="value",
                is_consistent=True
            )
    
    def test_invalid_average_confidence(self):
        """Test validation fails with invalid average confidence."""
        with pytest.raises(ValueError, match="average_confidence must be between 0.0 and 1.0"):
            FieldAggregation(
                field_name="test",
                field_type="text", 
                total_occurrences=1,
                pages_found={1},
                values=["value"],
                confidence_scores=[0.8],
                average_confidence=1.5,  # Invalid
                most_common_value="value",
                is_consistent=True
            )


class TestDocumentFieldSummary:
    """Test DocumentFieldSummary value object."""
    
    def test_valid_summary_creation(self):
        """Test creating valid DocumentFieldSummary."""
        summary = DocumentFieldSummary(
            total_fields=10,
            unique_field_names={"field1", "field2"},
            total_pages=3,
            field_aggregations=[],
            overall_confidence=0.75,
            fields_needing_review=2
        )
        
        assert summary.total_fields == 10
        assert summary.unique_field_names == {"field1", "field2"}
        assert summary.overall_confidence == 0.75
    
    def test_invalid_negative_total_fields(self):
        """Test validation fails with negative total fields."""
        with pytest.raises(ValueError, match="total_fields must be non-negative"):
            DocumentFieldSummary(
                total_fields=-1,  # Invalid
                unique_field_names=set(),
                total_pages=1,
                field_aggregations=[],
                overall_confidence=0.5,
                fields_needing_review=0
            )
    
    def test_invalid_negative_total_pages(self):
        """Test validation fails with negative total pages."""
        with pytest.raises(ValueError, match="total_pages must be non-negative"):
            DocumentFieldSummary(
                total_fields=0,
                unique_field_names=set(),
                total_pages=-1,  # Invalid
                field_aggregations=[],
                overall_confidence=0.5,
                fields_needing_review=0
            )
    
    def test_invalid_overall_confidence(self):
        """Test validation fails with invalid overall confidence."""
        with pytest.raises(ValueError, match="overall_confidence must be between 0.0 and 1.0"):
            DocumentFieldSummary(
                total_fields=0,
                unique_field_names=set(),
                total_pages=0,
                field_aggregations=[],
                overall_confidence=2.0,  # Invalid
                fields_needing_review=0
            )