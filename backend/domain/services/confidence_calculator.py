"""
ConfidenceCalculator domain service.

This service contains all confidence-related business logic including
bucket calculation, low confidence detection, and statistical aggregation.

This service works purely with domain entities and should NOT handle legacy data formats.
"""
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

from backend.domain.value_objects.confidence import Confidence
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.page_extraction import PageExtraction


@dataclass(frozen=True)
class ConfidenceStatistics:
    """
    Immutable statistics about confidence distribution.
    
    Attributes:
        buckets: List of counts per bucket (6 buckets: 0-0.2, 0.2-0.4, ..., 0.8-1.0)
        low_confidence_count: Number of items below low confidence threshold
        total_count: Total number of items analyzed
        average_confidence: Average confidence across all items
    """
    buckets: Tuple[int, ...]
    low_confidence_count: int
    total_count: int
    average_confidence: float
    
    def __post_init__(self):
        """Validate statistics consistency."""
        if len(self.buckets) != 6:
            raise ValueError("buckets must have exactly 6 elements")
        if sum(self.buckets) != self.total_count:
            raise ValueError("bucket counts must sum to total_count")
        if self.low_confidence_count > self.total_count:
            raise ValueError("low_confidence_count cannot exceed total_count")
        if not (0.0 <= self.average_confidence <= 1.0):
            raise ValueError("average_confidence must be between 0.0 and 1.0")


class ConfidenceCalculator:
    """
    Domain service for confidence-related calculations and business logic.
    
    This service centralizes:
    - Confidence bucket calculations for histograms
    - Low confidence threshold detection
    - Statistical aggregation across pages/fields
    - Business rules around confidence thresholds
    
    Works exclusively with domain entities (FieldExtraction, PageExtraction, etc.)
    """
    
    # Standard bucket boundaries for histogram display
    DEFAULT_BUCKET_BOUNDS = (0.2, 0.4, 0.6, 0.8, 1.0)
    
    def __init__(self, low_threshold: float = 0.4):
        """
        Initialize with confidence thresholds.
        
        Args:
            low_threshold: Confidence below which fields need review (default 0.4)
        """
        if not (0.0 <= low_threshold <= 1.0):
            raise ValueError("low_threshold must be between 0.0 and 1.0")
        self._low_threshold = low_threshold
    
    @property
    def low_threshold(self) -> float:
        """Get the low confidence threshold."""
        return self._low_threshold
    
    def is_low_confidence(self, confidence: Confidence) -> bool:
        """
        Check if confidence is considered low (needs review).
        
        Args:
            confidence: Confidence value to check
            
        Returns:
            True if confidence is at or below low threshold
        """
        return confidence.is_low(self._low_threshold)
    
    def calculate_field_statistics(self, fields: List[FieldExtraction]) -> ConfidenceStatistics:
        """
        Calculate comprehensive confidence statistics for a list of fields.
        
        Args:
            fields: List of FieldExtraction entities to analyze
            
        Returns:
            ConfidenceStatistics with buckets, counts, and averages
        """
        if not fields:
            return ConfidenceStatistics(
                buckets=(0, 0, 0, 0, 0, 0),
                low_confidence_count=0,
                total_count=0,
                average_confidence=0.0
            )
        
        buckets = [0] * 6
        low_count = 0
        confidence_sum = 0.0
        
        for field in fields:
            confidence = field.confidence
            
            bucket_index = confidence.bucket_index(self.DEFAULT_BUCKET_BOUNDS)
            buckets[bucket_index] += 1
            
            if self.is_low_confidence(confidence):
                low_count += 1
            
            confidence_sum += confidence.value
        
        total_count = len(fields)
        average_confidence = confidence_sum / total_count
        
        return ConfidenceStatistics(
            buckets=tuple(buckets),
            low_confidence_count=low_count,
            total_count=total_count,
            average_confidence=average_confidence
        )
    
    def calculate_page_statistics(self, pages: List[PageExtraction]) -> ConfidenceStatistics:
        """
        Calculate confidence statistics across multiple pages.
        
        Args:
            pages: List of PageExtraction entities to analyze
            
        Returns:
            Aggregated ConfidenceStatistics across all pages
        """
        if not pages:
            return ConfidenceStatistics(
                buckets=(0, 0, 0, 0, 0, 0),
                low_confidence_count=0,
                total_count=0,
                average_confidence=0.0
            )
        
        all_fields = []
        for page in pages:
            all_fields.extend(page.fields)
        
        return self.calculate_field_statistics(all_fields)
    
    def extract_low_confidence_fields(
        self, 
        pages: List[PageExtraction]
    ) -> List[Dict[str, Any]]:
        """
        Extract all low confidence fields from pages.
        
        Args:
            pages: List of PageExtraction entities to analyze
            
        Returns:
            List of low confidence field dictionaries with page and field info
        """
        results = []
        
        for page in pages:
            for field in page.fields:
                if self.is_low_confidence(field.confidence):
                    field_data = {
                        "page": page.page_number,
                        "name": field.field_name,
                        "value": field.value,
                        "confidence": field.confidence.value,
                    }
                    results.append(field_data)
        
        return results
    
    def aggregate_statistics(self, statistics: List[ConfidenceStatistics]) -> ConfidenceStatistics:
        """
        Aggregate multiple confidence statistics into a single result.
        
        Args:
            statistics: List of ConfidenceStatistics to combine
            
        Returns:
            Aggregated ConfidenceStatistics
        """
        if not statistics:
            return ConfidenceStatistics(
                buckets=(0, 0, 0, 0, 0, 0),
                low_confidence_count=0,
                total_count=0,
                average_confidence=0.0
            )
        
        # Sum buckets
        aggregated_buckets = [0] * 6
        total_low_count = 0
        total_count = 0
        weighted_confidence_sum = 0.0
        
        for stats in statistics:
            for i in range(6):
                aggregated_buckets[i] += stats.buckets[i]
            total_low_count += stats.low_confidence_count
            total_count += stats.total_count
            weighted_confidence_sum += stats.average_confidence * stats.total_count
        
        average_confidence = weighted_confidence_sum / total_count if total_count > 0 else 0.0
        
        return ConfidenceStatistics(
            buckets=tuple(aggregated_buckets),
            low_confidence_count=total_low_count,
            total_count=total_count,
            average_confidence=average_confidence
        )