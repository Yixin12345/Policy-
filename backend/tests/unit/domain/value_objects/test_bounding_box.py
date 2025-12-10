"""
Unit tests for BoundingBox value object
"""
import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parents[5]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.domain.value_objects.bounding_box import BoundingBox


class TestBoundingBoxCreation:
    """Test BoundingBox object creation and validation."""
    
    def test_valid_bounding_box(self):
        """Test creating bounding box with valid values."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        assert bbox.x == 0.1
        assert bbox.y == 0.2
        assert bbox.width == 0.3
        assert bbox.height == 0.4
    
    def test_zero_bounding_box(self):
        """Test creating bounding box at origin."""
        bbox = BoundingBox(0.0, 0.0, 0.0, 0.0)
        assert bbox.x == 0.0
        assert bbox.y == 0.0
        assert bbox.width == 0.0
        assert bbox.height == 0.0
    
    def test_full_image_bounding_box(self):
        """Test creating bounding box covering full image."""
        bbox = BoundingBox(0.0, 0.0, 1.0, 1.0)
        assert bbox.x == 0.0
        assert bbox.y == 0.0
        assert bbox.width == 1.0
        assert bbox.height == 1.0
    
    def test_clamps_x_high(self):
        """Test that x > 1.0 is clamped to 1.0."""
        bbox = BoundingBox(1.5, 0.5, 0.3, 0.4)
        assert bbox.x == 1.0
    
    def test_clamps_y_negative(self):
        """Test that negative y is clamped to 0.0."""
        bbox = BoundingBox(0.5, -0.5, 0.3, 0.4)
        assert bbox.y == 0.0
    
    def test_clamps_width_high(self):
        """Test that width > 1.0 is clamped to 1.0."""
        bbox = BoundingBox(0.1, 0.2, 1.5, 0.4)
        assert bbox.width == 1.0
    
    def test_clamps_height_negative(self):
        """Test that negative height is clamped to 0.0."""
        bbox = BoundingBox(0.1, 0.2, 0.3, -0.5)
        assert bbox.height == 0.0


class TestBoundingBoxFromDict:
    """Test BoundingBox.from_dict() factory method."""
    
    def test_from_dict_valid(self):
        """Test creating from valid dictionary."""
        data = {'x': 0.1, 'y': 0.2, 'width': 0.3, 'height': 0.4}
        bbox = BoundingBox.from_dict(data)
        assert bbox.x == 0.1
        assert bbox.y == 0.2
        assert bbox.width == 0.3
        assert bbox.height == 0.4
    
    def test_from_dict_missing_keys(self):
        """Test creating from dict with missing keys uses defaults."""
        bbox = BoundingBox.from_dict({'x': 0.5})
        assert bbox.x == 0.5
        assert bbox.y == 0.0
        assert bbox.width == 0.0
        assert bbox.height == 0.0
    
    def test_from_dict_clamped(self):
        """Test creating from dict with out-of-range values."""
        data = {'x': -0.5, 'y': 1.5, 'width': 0.5, 'height': 0.3}
        bbox = BoundingBox.from_dict(data)
        assert bbox.x == 0.0
        assert bbox.y == 1.0


class TestBoundingBoxFromAbsolute:
    """Test BoundingBox.from_absolute() factory method."""
    
    def test_from_absolute_valid(self):
        """Test creating from absolute pixel coordinates."""
        bbox = BoundingBox.from_absolute(100, 200, 300, 150, 1000, 800)
        assert bbox.x == 0.1
        assert bbox.y == 0.25
        assert bbox.width == 0.3
        assert bbox.height == 0.1875
    
    def test_from_absolute_zero_image(self):
        """Test creating from absolute with zero image dimensions."""
        bbox = BoundingBox.from_absolute(100, 200, 300, 150, 0, 0)
        assert bbox.x == 0.0
        assert bbox.y == 0.0
        assert bbox.width == 0.0
        assert bbox.height == 0.0


class TestBoundingBoxArea:
    """Test area() method."""
    
    def test_area_half_square(self):
        """Test area of half-image square."""
        bbox = BoundingBox(0.0, 0.0, 0.5, 0.5)
        assert bbox.area() == 0.25
    
    def test_area_full_image(self):
        """Test area of full image."""
        bbox = BoundingBox(0.0, 0.0, 1.0, 1.0)
        assert bbox.area() == 1.0
    
    def test_area_empty(self):
        """Test area of empty box."""
        bbox = BoundingBox(0.0, 0.0, 0.0, 0.0)
        assert bbox.area() == 0.0


class TestBoundingBoxCenter:
    """Test center() method."""
    
    def test_center_at_origin(self):
        """Test center of box at origin."""
        bbox = BoundingBox(0.0, 0.0, 0.4, 0.4)
        assert bbox.center() == (0.2, 0.2)
    
    def test_center_offset(self):
        """Test center of offset box."""
        bbox = BoundingBox(0.2, 0.3, 0.6, 0.4)
        assert bbox.center() == (0.5, 0.5)


class TestBoundingBoxBottomRight:
    """Test bottom_right() method."""
    
    def test_bottom_right(self):
        """Test bottom-right coordinates."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        x2, y2 = bbox.bottom_right()
        assert abs(x2 - 0.4) < 1e-10
        assert abs(y2 - 0.6) < 1e-10


class TestBoundingBoxOverlaps:
    """Test overlaps() method."""
    
    def test_overlaps_true(self):
        """Test boxes that overlap."""
        box1 = BoundingBox(0.0, 0.0, 0.5, 0.5)
        box2 = BoundingBox(0.3, 0.3, 0.5, 0.5)
        assert box1.overlaps(box2)
        assert box2.overlaps(box1)
    
    def test_overlaps_false(self):
        """Test boxes that don't overlap."""
        box1 = BoundingBox(0.0, 0.0, 0.5, 0.5)
        box2 = BoundingBox(0.6, 0.6, 0.3, 0.3)
        assert not box1.overlaps(box2)
        assert not box2.overlaps(box1)
    
    def test_overlaps_touching(self):
        """Test boxes that touch at edge."""
        box1 = BoundingBox(0.0, 0.0, 0.5, 0.5)
        box2 = BoundingBox(0.5, 0.0, 0.5, 0.5)
        assert not box1.overlaps(box2)


class TestBoundingBoxContainsPoint:
    """Test contains_point() method."""
    
    def test_contains_point_inside(self):
        """Test point inside box."""
        bbox = BoundingBox(0.2, 0.2, 0.4, 0.4)
        assert bbox.contains_point(0.3, 0.3)
    
    def test_contains_point_outside(self):
        """Test point outside box."""
        bbox = BoundingBox(0.2, 0.2, 0.4, 0.4)
        assert not bbox.contains_point(0.1, 0.1)
    
    def test_contains_point_on_edge(self):
        """Test point on edge of box."""
        bbox = BoundingBox(0.2, 0.2, 0.4, 0.4)
        assert bbox.contains_point(0.2, 0.2)
        assert bbox.contains_point(0.6, 0.6)


class TestBoundingBoxValidation:
    """Test is_valid() and is_empty() methods."""
    
    def test_is_valid_true(self):
        """Test valid bounding box."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        assert bbox.is_valid()
    
    def test_is_valid_false_zero_width(self):
        """Test invalid box with zero width."""
        bbox = BoundingBox(0.1, 0.2, 0.0, 0.4)
        assert not bbox.is_valid()
    
    def test_is_empty_true(self):
        """Test empty bounding box."""
        bbox = BoundingBox(0.0, 0.0, 0.0, 0.0)
        assert bbox.is_empty()
    
    def test_is_empty_false(self):
        """Test non-empty bounding box."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        assert not bbox.is_empty()


class TestBoundingBoxConversions:
    """Test to_dict() and to_absolute() methods."""
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        data = bbox.to_dict()
        assert data == {'x': 0.1, 'y': 0.2, 'width': 0.3, 'height': 0.4}
    
    def test_to_absolute(self):
        """Test converting to absolute coordinates."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        abs_coords = bbox.to_absolute(1000, 800)
        assert abs_coords == (100, 160, 300, 320)


class TestBoundingBoxStringRepresentation:
    """Test string representation."""
    
    def test_str_representation(self):
        """Test string representation."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        assert str(bbox) == "BBox(x=0.10, y=0.20, w=0.30, h=0.40)"


class TestBoundingBoxImmutability:
    """Test that BoundingBox is immutable."""
    
    def test_cannot_modify_x(self):
        """Test that x cannot be changed after creation."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        with pytest.raises(AttributeError):
            bbox.x = 0.5  # type: ignore
    
    def test_cannot_modify_width(self):
        """Test that width cannot be changed after creation."""
        bbox = BoundingBox(0.1, 0.2, 0.3, 0.4)
        with pytest.raises(AttributeError):
            bbox.width = 0.5  # type: ignore
