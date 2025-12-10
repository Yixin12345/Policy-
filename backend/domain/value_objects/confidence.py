"""
Confidence value object

Represents a confidence score between 0 and 1 (inclusive).
Immutable and self-validating.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple


@dataclass(frozen=True)
class Confidence:
    """
    Immutable confidence value between 0 and 1.
    
    Automatically clamps values to valid range [0, 1].
    Provides domain-specific methods for confidence analysis.
    """
    value: float
    
    def __post_init__(self):
        """Validate and clamp confidence to [0, 1] range."""
        if not isinstance(self.value, (int, float)):
            object.__setattr__(self, 'value', 0.0)
        elif self.value < 0.0:
            object.__setattr__(self, 'value', 0.0)
        elif self.value > 1.0:
            object.__setattr__(self, 'value', 1.0)
        else:
            object.__setattr__(self, 'value', float(self.value))
    
    @classmethod
    def from_raw(cls, raw_value: Any) -> Confidence:
        """
        Create Confidence from any value, coercing to valid range.
        
        Args:
            raw_value: Any value that can be converted to float
            
        Returns:
            Confidence instance with clamped value
            
        Examples:
            >>> Confidence.from_raw(0.8)
            Confidence(value=0.8)
            >>> Confidence.from_raw("0.75")
            Confidence(value=0.75)
            >>> Confidence.from_raw("invalid")
            Confidence(value=0.0)
            >>> Confidence.from_raw(1.5)
            Confidence(value=1.0)
        """
        try:
            value = float(raw_value)
            return cls(value)
        except (TypeError, ValueError, AttributeError):
            return cls(0.0)
    
    def is_low(self, threshold: float = 0.4) -> bool:
        """
        Check if confidence is below threshold (indicates needs review).
        
        Args:
            threshold: Confidence threshold (default 0.4)
            
        Returns:
            True if confidence <= threshold
        """
        return self.value <= threshold
    
    def is_high(self, threshold: float = 0.8) -> bool:
        """
        Check if confidence is above threshold (indicates high quality).
        
        Args:
            threshold: Confidence threshold (default 0.8)
            
        Returns:
            True if confidence >= threshold
        """
        return self.value >= threshold
    
    def bucket_index(
        self, 
        bounds: Tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 1.0)
    ) -> int:
        """
        Get bucket index for histogram grouping.
        
        Args:
            bounds: Tuple of boundary values
            
        Returns:
            Index of the bucket this confidence falls into
            
        Examples:
            >>> Confidence(0.1).bucket_index()
            0  # 0.0-0.2 bucket
            >>> Confidence(0.3).bucket_index()
            1  # 0.2-0.4 bucket
            >>> Confidence(1.0).bucket_index()
            4  # 0.8-1.0 bucket
        """
        for idx, bound in enumerate(bounds):
            if self.value <= bound:
                return idx
        return len(bounds)
    
    def is_perfect(self) -> bool:
        """Check if confidence is exactly 1.0 (perfect match)."""
        return self.value == 1.0
    
    def is_zero(self) -> bool:
        """Check if confidence is exactly 0.0 (no confidence)."""
        return self.value == 0.0
    
    def percentage(self) -> float:
        """Get confidence as percentage (0-100)."""
        return self.value * 100.0
    
    def __str__(self) -> str:
        """String representation showing 2 decimal places."""
        return f"{self.value:.2f}"
    
    def __float__(self) -> float:
        """Convert to float for numerical operations."""
        return self.value
    
    def __lt__(self, other: Confidence | float) -> bool:
        """Compare confidence values."""
        other_val = other.value if isinstance(other, Confidence) else float(other)
        return self.value < other_val
    
    def __le__(self, other: Confidence | float) -> bool:
        """Compare confidence values."""
        other_val = other.value if isinstance(other, Confidence) else float(other)
        return self.value <= other_val
    
    def __gt__(self, other: Confidence | float) -> bool:
        """Compare confidence values."""
        other_val = other.value if isinstance(other, Confidence) else float(other)
        return self.value > other_val
    
    def __ge__(self, other: Confidence | float) -> bool:
        """Compare confidence values."""
        other_val = other.value if isinstance(other, Confidence) else float(other)
        return self.value >= other_val
