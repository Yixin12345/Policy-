"""
Unit tests for ConfidenceCalculator domain service.

Tests confidence calculation business logic without any dependencies on legacy code.
"""
import pytest
from backend.domain.services.confidence_calculator import ConfidenceCalculator, ConfidenceStatistics
from backend.domain.value_objects.confidence import Confidence
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.value_objects.bounding_box import BoundingBox


@pytest.fixture
def calculator():
    """Create a ConfidenceCalculator with default threshold."""
    return ConfidenceCalculator(low_threshold=0.4)


@pytest.fixture
def custom_calculator():
    """Create a ConfidenceCalculator with custom threshold."""
    return ConfidenceCalculator(low_threshold=0.3)


@pytest.fixture
def sample_fields():
    """Create sample field extractions for testing."""
    return [
        FieldExtraction.create(
            field_name="field1", 
            value="value1", 
            confidence=0.1
        ),
        FieldExtraction.create(
            field_name="field2", 
            value="value2", 
            confidence=0.3
        ),
        FieldExtraction.create(
            field_name="field3", 
            value="value3", 
            confidence=0.5
        ),
        FieldExtraction.create(
            field_name="field4", 
            value="value4", 
            confidence=0.7
        ),
        FieldExtraction.create(
            field_name="field5", 
            value="value5", 
            confidence=0.9
        ),
        FieldExtraction.create(
            field_name="field6", 
            value="value6", 
            confidence=1.0
        )
    ]


@pytest.fixture
def sample_pages(sample_fields):
    """Create sample page extractions for testing."""
    # Page 1: First 3 fields
    page1 = PageExtraction.create(
        page_number=1,
        fields=sample_fields[:3],
        tables=[]
    )
    
    # Page 2: Last 3 fields
    page2 = PageExtraction.create(
        page_number=2,
        fields=sample_fields[3:],
        tables=[]
    )
    
    return [page1, page2]


class TestConfidenceCalculatorInitialization:
    """Test ConfidenceCalculator initialization."""
    
    def test_default_initialization(self):
        """Test default initialization with valid threshold."""
        calculator = ConfidenceCalculator(low_threshold=0.4)
        assert calculator.low_threshold == 0.4
    
    def test_custom_threshold(self):
        """Test initialization with custom threshold."""
        calculator = ConfidenceCalculator(low_threshold=0.3)
        assert calculator.low_threshold == 0.3
    
    def test_invalid_threshold_low(self):
        """Test initialization with invalid low threshold."""
        with pytest.raises(ValueError, match="low_threshold must be between 0.0 and 1.0"):
            ConfidenceCalculator(low_threshold=-0.1)
    
    def test_invalid_threshold_high(self):
        """Test initialization with invalid high threshold."""
        with pytest.raises(ValueError, match="low_threshold must be between 0.0 and 1.0"):
            ConfidenceCalculator(low_threshold=1.1)
    
    def test_boundary_thresholds(self):
        """Test boundary threshold values."""
        calculator_zero = ConfidenceCalculator(low_threshold=0.0)
        assert calculator_zero.low_threshold == 0.0
        
        calculator_one = ConfidenceCalculator(low_threshold=1.0)
        assert calculator_one.low_threshold == 1.0


class TestIsLowConfidence:
    """Test low confidence detection."""
    
    def test_is_low_confidence_true(self, calculator):
        """Test detection of low confidence values."""
        assert calculator.is_low_confidence(Confidence.from_raw(0.1)) is True
        assert calculator.is_low_confidence(Confidence.from_raw(0.3)) is True
        assert calculator.is_low_confidence(Confidence.from_raw(0.4)) is True  # Equal to threshold
    
    def test_is_low_confidence_false(self, calculator):
        """Test detection of high confidence values."""
        assert calculator.is_low_confidence(Confidence.from_raw(0.5)) is False
        assert calculator.is_low_confidence(Confidence.from_raw(0.8)) is False
        assert calculator.is_low_confidence(Confidence.from_raw(1.0)) is False
    
    def test_is_low_confidence_custom_threshold(self, custom_calculator):
        """Test low confidence detection with custom threshold."""
        # Threshold is 0.3
        assert custom_calculator.is_low_confidence(Confidence.from_raw(0.1)) is True
        assert custom_calculator.is_low_confidence(Confidence.from_raw(0.3)) is True
        assert custom_calculator.is_low_confidence(Confidence.from_raw(0.4)) is False


class TestCalculateFieldStatistics:
    """Test field statistics calculation."""
    
    def test_calculate_empty_fields(self, calculator):
        """Test calculation with empty fields list."""
        stats = calculator.calculate_field_statistics([])
        
        assert stats.buckets == (0, 0, 0, 0, 0, 0)
        assert stats.low_confidence_count == 0
        assert stats.total_count == 0
        assert stats.average_confidence == 0.0
    
    def test_calculate_field_statistics_complete(self, calculator, sample_fields):
        """Test calculation with sample fields."""
        stats = calculator.calculate_field_statistics(sample_fields)
        
        # Expected buckets: 0.1->bucket0, 0.3->bucket1, 0.5->bucket2, 0.7->bucket3, 0.9->bucket4, 1.0->bucket4
        assert stats.buckets == (1, 1, 1, 1, 2, 0)  # Last bucket is 0.8-1.0, so 0.9 and 1.0 both go there
        assert stats.low_confidence_count == 2  # 0.1, 0.3 are <= 0.4 (threshold); 0.5 > 0.4
        assert stats.total_count == 6
        # Average: (0.1 + 0.3 + 0.5 + 0.7 + 0.9 + 1.0) / 6 = 3.5 / 6 ≈ 0.583
        assert abs(stats.average_confidence - (3.5 / 6)) < 0.001
    
    def test_calculate_field_statistics_single_field(self, calculator):
        """Test calculation with single field."""
        field = FieldExtraction.create(
            field_name="test", 
            value="test", 
            confidence=0.6
        )
        
        stats = calculator.calculate_field_statistics([field])
        
        assert stats.buckets == (0, 0, 1, 0, 0, 0)  # 0.6 goes to bucket 2 (0.4-0.6)
        assert stats.low_confidence_count == 0
        assert stats.total_count == 1
        assert stats.average_confidence == 0.6


class TestCalculatePageStatistics:
    """Test page statistics calculation."""
    
    def test_calculate_empty_pages(self, calculator):
        """Test calculation with empty pages list."""
        stats = calculator.calculate_page_statistics([])
        
        assert stats.buckets == (0, 0, 0, 0, 0, 0)
        assert stats.low_confidence_count == 0
        assert stats.total_count == 0
        assert stats.average_confidence == 0.0
    
    def test_calculate_page_statistics_complete(self, calculator, sample_pages):
        """Test calculation across multiple pages."""
        stats = calculator.calculate_page_statistics(sample_pages)
        
        # Same as field statistics since we're aggregating all fields
        assert stats.buckets == (1, 1, 1, 1, 2, 0)
        assert stats.low_confidence_count == 2  # Only field1(0.1) and field2(0.3) are <= 0.4
        assert stats.total_count == 6
        assert abs(stats.average_confidence - (3.5 / 6)) < 0.001
    
    def test_calculate_page_statistics_single_page(self, calculator, sample_fields):
        """Test calculation with single page."""
        page = PageExtraction.create(
            page_number=1,
            fields=sample_fields[:2],  # Only first 2 fields
            tables=[]
        )
        
        stats = calculator.calculate_page_statistics([page])
        
        assert stats.buckets == (1, 1, 0, 0, 0, 0)  # 0.1 and 0.3
        assert stats.low_confidence_count == 2
        assert stats.total_count == 2
        assert stats.average_confidence == 0.2  # (0.1 + 0.3) / 2


class TestExtractLowConfidenceFields:
    """Test low confidence field extraction."""
    
    def test_extract_empty_pages(self, calculator):
        """Test extraction from empty pages."""
        results = calculator.extract_low_confidence_fields([])
        assert results == []
    
    def test_extract_low_confidence_fields(self, calculator, sample_pages):
        """Test extraction of low confidence fields."""
        results = calculator.extract_low_confidence_fields(sample_pages)
        
        # Should extract fields with confidence <= 0.4: field1(0.1), field2(0.3)
        assert len(results) == 2  # field1 and field2 are <= 0.4 threshold
        
        # Check first result
        field1_result = next(r for r in results if r["name"] == "field1")
        assert field1_result["page"] == 1
        assert field1_result["value"] == "value1"
        assert field1_result["confidence"] == 0.1
        
        # Check second result
        field2_result = next(r for r in results if r["name"] == "field2")
        assert field2_result["page"] == 1
        assert field2_result["value"] == "value2"
        assert field2_result["confidence"] == 0.3
    
    def test_extract_no_low_confidence_fields(self):
        """Test extraction when no fields are low confidence."""
        calculator = ConfidenceCalculator(low_threshold=0.05)  # Very low threshold
        
        fields = [
            FieldExtraction.create(
                field_name="high1", 
                value="value1", 
                confidence=0.8
            ),
            FieldExtraction.create(
                field_name="high2", 
                value="value2", 
                confidence=0.9
            )
        ]
        
        page = PageExtraction.create(page_number=1, fields=fields, tables=[])
        results = calculator.extract_low_confidence_fields([page])
        
        assert results == []


class TestAggregateStatistics:
    """Test statistics aggregation."""
    
    def test_aggregate_empty_list(self, calculator):
        """Test aggregation of empty statistics list."""
        result = calculator.aggregate_statistics([])
        
        assert result.buckets == (0, 0, 0, 0, 0, 0)
        assert result.low_confidence_count == 0
        assert result.total_count == 0
        assert result.average_confidence == 0.0
    
    def test_aggregate_single_statistics(self, calculator):
        """Test aggregation of single statistics object."""
        stats = ConfidenceStatistics(
            buckets=(1, 2, 3, 4, 5, 6),
            low_confidence_count=10,
            total_count=21,
            average_confidence=0.6
        )
        
        result = calculator.aggregate_statistics([stats])
        
        assert result.buckets == (1, 2, 3, 4, 5, 6)
        assert result.low_confidence_count == 10
        assert result.total_count == 21
        assert result.average_confidence == 0.6
    
    def test_aggregate_multiple_statistics(self, calculator):
        """Test aggregation of multiple statistics objects."""
        stats1 = ConfidenceStatistics(
            buckets=(1, 1, 1, 1, 1, 1),
            low_confidence_count=2,
            total_count=6,
            average_confidence=0.5
        )
        
        stats2 = ConfidenceStatistics(
            buckets=(2, 2, 2, 2, 2, 2),
            low_confidence_count=4,
            total_count=12,
            average_confidence=0.6
        )
        
        result = calculator.aggregate_statistics([stats1, stats2])
        
        assert result.buckets == (3, 3, 3, 3, 3, 3)
        assert result.low_confidence_count == 6
        assert result.total_count == 18
        
        # Weighted average: (0.5 * 6 + 0.6 * 12) / 18 = (3 + 7.2) / 18 = 10.2 / 18 ≈ 0.567
        expected_avg = (0.5 * 6 + 0.6 * 12) / 18
        assert abs(result.average_confidence - expected_avg) < 0.001


class TestConfidenceStatistics:
    """Test ConfidenceStatistics validation."""
    
    def test_valid_statistics(self):
        """Test creation of valid statistics object."""
        stats = ConfidenceStatistics(
            buckets=(1, 2, 3, 4, 5, 6),
            low_confidence_count=5,
            total_count=21,
            average_confidence=0.6
        )
        
        assert stats.buckets == (1, 2, 3, 4, 5, 6)
        assert stats.low_confidence_count == 5
        assert stats.total_count == 21
        assert stats.average_confidence == 0.6
    
    def test_invalid_bucket_count(self):
        """Test validation of bucket count."""
        with pytest.raises(ValueError, match="buckets must have exactly 6 elements"):
            ConfidenceStatistics(
                buckets=(1, 2, 3, 4, 5),  # Only 5 elements
                low_confidence_count=5,
                total_count=15,
                average_confidence=0.6
            )
    
    def test_invalid_bucket_sum(self):
        """Test validation that buckets sum to total_count."""
        with pytest.raises(ValueError, match="bucket counts must sum to total_count"):
            ConfidenceStatistics(
                buckets=(1, 2, 3, 4, 5, 6),  # Sum is 21
                low_confidence_count=5,
                total_count=20,  # Doesn't match sum
                average_confidence=0.6
            )
    
    def test_invalid_low_confidence_count(self):
        """Test validation that low_confidence_count doesn't exceed total."""
        with pytest.raises(ValueError, match="low_confidence_count cannot exceed total_count"):
            ConfidenceStatistics(
                buckets=(1, 2, 3, 4, 5, 6),
                low_confidence_count=25,  # Exceeds total_count
                total_count=21,
                average_confidence=0.6
            )
    
    def test_invalid_average_confidence_low(self):
        """Test validation of average confidence range (too low)."""
        with pytest.raises(ValueError, match="average_confidence must be between 0.0 and 1.0"):
            ConfidenceStatistics(
                buckets=(1, 2, 3, 4, 5, 6),
                low_confidence_count=5,
                total_count=21,
                average_confidence=-0.1
            )
    
    def test_invalid_average_confidence_high(self):
        """Test validation of average confidence range (too high)."""
        with pytest.raises(ValueError, match="average_confidence must be between 0.0 and 1.0"):
            ConfidenceStatistics(
                buckets=(1, 2, 3, 4, 5, 6),
                low_confidence_count=5,
                total_count=21,
                average_confidence=1.1
            )