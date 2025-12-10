"""
BoundingBox value object

Represents normalized coordinates for a rectangular region.
All coordinates are normalized to [0, 1] range.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class BoundingBox:
    """
    Immutable bounding box with normalized coordinates [0, 1].
    
    Represents a rectangular region where:
    - x, y: top-left corner (normalized)
    - width, height: dimensions (normalized)
    
    All values are automatically clamped to valid [0, 1] range.
    """
    x: float
    y: float
    width: float
    height: float
    
    def __post_init__(self):
        """Keep values as-is from input without normalization or conversion."""
        # Store values exactly as provided, no conversion to float or clamping
        for field_name in ['x', 'y', 'width', 'height']:
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                object.__setattr__(self, field_name, 0)
            # Keep original value type (int or float) as provided
            # No normalization, no clamping to [0, 1]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> BoundingBox:
        """
        Create BoundingBox from dictionary.
        
        Args:
            data: Dict with keys 'x', 'y', 'width', 'height'
            
        Returns:
            BoundingBox instance with clamped values
            
        Examples:
            >>> BoundingBox.from_dict({'x': 0.1, 'y': 0.2, 'width': 0.5, 'height': 0.3})
            BoundingBox(x=0.1, y=0.2, width=0.5, height=0.3)
            >>> BoundingBox.from_dict({'x': -0.5, 'y': 1.5, 'width': 0.5, 'height': 0.3})
            BoundingBox(x=0.0, y=1.0, width=0.5, height=0.3)
        """
        if not data:
            return cls(0, 0, 0, 0)

        return cls(
            x=data.get('x', 0),
            y=data.get('y', 0),
            width=data.get('width', 0),
            height=data.get('height', 0)
        )
    
    @classmethod
    def from_absolute(
        cls,
        x: float,
        y: float,
        width: float,
        height: float,
        image_width: int,
        image_height: int
    ) -> BoundingBox:
        """
        Create BoundingBox from absolute pixel coordinates.
        
        Args:
            x, y: Top-left corner in pixels
            width, height: Dimensions in pixels
            image_width, image_height: Image dimensions for normalization
            
        Returns:
            BoundingBox with normalized coordinates
            
        Examples:
            >>> BoundingBox.from_absolute(100, 200, 300, 150, 1000, 800)
            BoundingBox(x=0.1, y=0.25, width=0.3, height=0.1875)
        """
        if image_width <= 0 or image_height <= 0:
            return cls(0.0, 0.0, 0.0, 0.0)
        
        return cls(
            x=x / image_width,
            y=y / image_height,
            width=width / image_width,
            height=height / image_height
        )
    
    def area(self) -> float:
        """
        Calculate normalized area of bounding box.
        
        Returns:
            Area as fraction of total image (0 to 1)
            
        Examples:
            >>> BoundingBox(0.0, 0.0, 0.5, 0.5).area()
            0.25
            >>> BoundingBox(0.0, 0.0, 1.0, 1.0).area()
            1.0
        """
        return self.width * self.height
    
    def center(self) -> Tuple[float, float]:
        """
        Get center point of bounding box.
        
        Returns:
            Tuple of (center_x, center_y) in normalized coordinates
            
        Examples:
            >>> BoundingBox(0.0, 0.0, 0.4, 0.4).center()
            (0.2, 0.2)
            >>> BoundingBox(0.2, 0.3, 0.6, 0.4).center()
            (0.5, 0.5)
        """
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    def bottom_right(self) -> Tuple[float, float]:
        """
        Get bottom-right corner coordinates.
        
        Returns:
            Tuple of (x2, y2) in normalized coordinates
            
        Examples:
            >>> BoundingBox(0.1, 0.2, 0.3, 0.4).bottom_right()
            (0.4, 0.6)
        """
        return (self.x + self.width, self.y + self.height)
    
    def overlaps(self, other: BoundingBox) -> bool:
        """
        Check if this bounding box overlaps with another.
        
        Args:
            other: Another BoundingBox to check
            
        Returns:
            True if boxes overlap
            
        Examples:
            >>> box1 = BoundingBox(0.0, 0.0, 0.5, 0.5)
            >>> box2 = BoundingBox(0.3, 0.3, 0.5, 0.5)
            >>> box1.overlaps(box2)
            True
            >>> box3 = BoundingBox(0.6, 0.6, 0.3, 0.3)
            >>> box1.overlaps(box3)
            False
        """
        x1, y1 = self.x, self.y
        x2, y2 = self.bottom_right()
        
        ox1, oy1 = other.x, other.y
        ox2, oy2 = other.bottom_right()
        
        return not (x2 <= ox1 or x1 >= ox2 or y2 <= oy1 or y1 >= oy2)
    
    def contains_point(self, x: float, y: float) -> bool:
        """
        Check if a point is inside this bounding box.
        
        Args:
            x, y: Point coordinates (normalized)
            
        Returns:
            True if point is inside box
            
        Examples:
            >>> box = BoundingBox(0.2, 0.2, 0.4, 0.4)
            >>> box.contains_point(0.3, 0.3)
            True
            >>> box.contains_point(0.1, 0.1)
            False
        """
        x2, y2 = self.bottom_right()
        return self.x <= x <= x2 and self.y <= y <= y2
    
    def is_valid(self) -> bool:
        """
        Check if bounding box has valid dimensions.
        
        Returns:
            True if width and height are > 0
        """
        return self.width > 0 and self.height > 0
    
    def is_empty(self) -> bool:
        """
        Check if bounding box is empty (zero area).
        
        Returns:
            True if width or height is 0
        """
        return self.width == 0 or self.height == 0
    
    def to_dict(self) -> Dict[str, float]:
        """
        Convert to dictionary representation.
        
        Returns:
            Dict with 'x', 'y', 'width', 'height' keys
        """
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height
        }
    
    def to_absolute(self, image_width: int, image_height: int) -> Tuple[int, int, int, int]:
        """
        Convert to absolute pixel coordinates.
        
        Args:
            image_width, image_height: Image dimensions
            
        Returns:
            Tuple of (x, y, width, height) in pixels
            
        Examples:
            >>> box = BoundingBox(0.1, 0.2, 0.3, 0.4)
            >>> box.to_absolute(1000, 800)
            (100, 160, 300, 320)
        """
        return (
            int(self.x * image_width),
            int(self.y * image_height),
            int(self.width * image_width),
            int(self.height * image_height)
        )
    
    def __str__(self) -> str:
        """String representation showing 2 decimal places."""
        return f"BBox(x={self.x:.2f}, y={self.y:.2f}, w={self.width:.2f}, h={self.height:.2f})"
