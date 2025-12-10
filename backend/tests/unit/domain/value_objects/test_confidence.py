"""
Unit tests for Confidence value object
"""
import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parents[5]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.domain.value_objects.confidence import Confidence


class TestConfidenceCreation:
    """Test Confidence object creation and validation."""
    
    def test_valid_confidence(self):
        """Test creating confidence with valid value."""
        conf = Confidence(0.8)
        assert conf.value == 0.8
    
    def test_zero_confidence(self):
        """Test creating confidence with 0.0."""
        conf = Confidence(0.0)
        assert conf.value == 0.0
    
    def test_perfect_confidence(self):
        """Test creating confidence with 1.0."""
        conf = Confidence(1.0)
        assert conf.value == 1.0
    
    def test_clamps_high_value(self):
        """Test that values > 1.0 are clamped to 1.0."""
        conf = Confidence(1.5)
        assert conf.value == 1.0
    
    def test_clamps_negative_value(self):
        """Test that negative values are clamped to 0.0."""
        conf = Confidence(-0.5)
        assert conf.value == 0.0


class TestConfidenceFromRaw:
    """Test Confidence.from_raw() factory method."""
    
    def test_from_float(self):
        """Test creating from float."""
        conf = Confidence.from_raw(0.75)
        assert conf.value == 0.75
    
    def test_from_string_valid(self):
        """Test creating from valid string."""
        conf = Confidence.from_raw("0.75")
        assert conf.value == 0.75
    
    def test_from_string_invalid(self):
        """Test creating from invalid string returns 0.0."""
        conf = Confidence.from_raw("invalid")
        assert conf.value == 0.0
    
    def test_from_none(self):
        """Test creating from None returns 0.0."""
        conf = Confidence.from_raw(None)
        assert conf.value == 0.0


class TestConfidenceThresholds:
    """Test confidence threshold methods."""
    
    def test_is_low_default_threshold(self):
        """Test is_low() with default threshold (0.4)."""
        assert Confidence(0.3).is_low()
        assert Confidence(0.4).is_low()
        assert not Confidence(0.5).is_low()
    
    def test_is_high_default_threshold(self):
        """Test is_high() with default threshold (0.8)."""
        assert not Confidence(0.7).is_high()
        assert Confidence(0.8).is_high()
        assert Confidence(0.9).is_high()
    
    def test_is_perfect(self):
        """Test is_perfect() method."""
        assert Confidence(1.0).is_perfect()
        assert not Confidence(0.99).is_perfect()
    
    def test_is_zero(self):
        """Test is_zero() method."""
        assert Confidence(0.0).is_zero()
        assert not Confidence(0.01).is_zero()


class TestConfidenceBuckets:
    """Test bucket_index() method for histograms."""
    
    def test_bucket_index_default_bounds(self):
        """Test bucket_index with default bounds."""
        assert Confidence(0.1).bucket_index() == 0  # 0.0-0.2
        assert Confidence(0.3).bucket_index() == 1  # 0.2-0.4
        assert Confidence(0.5).bucket_index() == 2  # 0.4-0.6
        assert Confidence(0.7).bucket_index() == 3  # 0.6-0.8
        assert Confidence(0.9).bucket_index() == 4  # 0.8-1.0
        assert Confidence(1.0).bucket_index() == 4  # exactly at boundary


class TestConfidenceHelpers:
    """Test helper methods."""
    
    def test_percentage(self):
        """Test percentage() method."""
        assert Confidence(0.75).percentage() == 75.0
        assert Confidence(1.0).percentage() == 100.0
    
    def test_str_representation(self):
        """Test string representation."""
        assert str(Confidence(0.8)) == "0.80"
        assert str(Confidence(1.0)) == "1.00"
    
    def test_float_conversion(self):
        """Test float conversion."""
        conf = Confidence(0.75)
        assert float(conf) == 0.75


class TestConfidenceComparison:
    """Test comparison operators."""
    
    def test_less_than_confidence(self):
        """Test < operator with another Confidence."""
        assert Confidence(0.5) < Confidence(0.7)
        assert not Confidence(0.7) < Confidence(0.5)
    
    def test_less_than_float(self):
        """Test < operator with float."""
        assert Confidence(0.5) < 0.7
        assert not Confidence(0.7) < 0.5
    
    def test_greater_than(self):
        """Test > operator."""
        assert Confidence(0.7) > Confidence(0.5)
        assert not Confidence(0.5) > Confidence(0.7)


class TestConfidenceImmutability:
    """Test that Confidence is immutable."""
    
    def test_cannot_modify_value(self):
        """Test that confidence value cannot be changed after creation."""
        conf = Confidence(0.5)
        with pytest.raises(AttributeError):
            conf.value = 0.7  # type: ignore
