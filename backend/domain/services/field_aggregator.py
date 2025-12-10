"""
FieldAggregator domain service.

This service contains business logic for aggregating and organizing field data
across multiple pages and documents for analysis and reporting purposes.

This service works purely with domain entities and should NOT handle legacy data formats.
"""
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple, Any
from collections import defaultdict

from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.value_objects.confidence import Confidence


@dataclass(frozen=True)
class FieldAggregation:
    """
    Immutable aggregation of field data across pages.
    
    Provides summary statistics and collections for a specific field type.
    """
    field_name: str
    field_type: str
    total_occurrences: int
    pages_found: Set[int]
    values: List[str]  # All unique values found
    confidence_scores: List[float]
    average_confidence: float
    most_common_value: Optional[str]
    is_consistent: bool  # True if all values are the same
    
    def __post_init__(self):
        """Validate aggregation data consistency."""
        if self.total_occurrences != len(self.confidence_scores):
            raise ValueError("total_occurrences must equal length of confidence_scores")
        if self.total_occurrences > 0 and not (0.0 <= self.average_confidence <= 1.0):
            raise ValueError("average_confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class DocumentFieldSummary:
    """
    Immutable summary of all fields extracted from a document.
    
    Provides high-level statistics for analysis and dashboard purposes.
    """
    total_fields: int
    unique_field_names: Set[str]
    total_pages: int
    field_aggregations: List[FieldAggregation]
    overall_confidence: float
    fields_needing_review: int
    
    def __post_init__(self):
        """Validate summary data consistency."""
        if self.total_fields < 0:
            raise ValueError("total_fields must be non-negative")
        if self.total_pages < 0:
            raise ValueError("total_pages must be non-negative")
        if not (0.0 <= self.overall_confidence <= 1.0):
            raise ValueError("overall_confidence must be between 0.0 and 1.0")


class FieldAggregator:
    """
    Domain service for field aggregation and analysis across pages.
    
    This service centralizes:
    - Field grouping by name/type across pages
    - Value consistency analysis
    - Cross-page field statistics
    - Field coverage analysis
    
    Works exclusively with domain entities (FieldExtraction, PageExtraction)
    """
    
    def __init__(self, low_confidence_threshold: float = 0.4):
        """
        Initialize with configuration.
        
        Args:
            low_confidence_threshold: Confidence below which fields need review
        """
        if not (0.0 <= low_confidence_threshold <= 1.0):
            raise ValueError("low_confidence_threshold must be between 0.0 and 1.0")
        self._low_confidence_threshold = low_confidence_threshold
    
    @property
    def low_confidence_threshold(self) -> float:
        """Get the low confidence threshold."""
        return self._low_confidence_threshold
    
    def aggregate_fields_by_name(self, pages: List[PageExtraction]) -> Dict[str, FieldAggregation]:
        """
        Aggregate fields by name across all pages.
        
        Args:
            pages: List of PageExtraction entities to analyze
            
        Returns:
            Dictionary mapping field names to their aggregations
        """
        if not pages:
            return {}
        
        # Group fields by name
        fields_by_name = defaultdict(list)
        for page in pages:
            for field in page.fields:
                fields_by_name[field.field_name].append((field, page.page_number))
        
        # Create aggregations
        aggregations = {}
        for field_name, field_data in fields_by_name.items():
            aggregations[field_name] = self._create_field_aggregation(field_name, field_data)
        
        return aggregations
    
    def aggregate_fields_by_type(self, pages: List[PageExtraction]) -> Dict[str, FieldAggregation]:
        """
        Aggregate fields by type across all pages.
        
        Args:
            pages: List of PageExtraction entities to analyze
            
        Returns:
            Dictionary mapping field types to their aggregations
        """
        if not pages:
            return {}
        
        # Group fields by type
        fields_by_type = defaultdict(list)
        for page in pages:
            for field in page.fields:
                fields_by_type[field.field_type].append((field, page.page_number))
        
        # Create aggregations (using field_type as the key)
        aggregations = {}
        for field_type, field_data in fields_by_type.items():
            # For type aggregations, use the type as the name
            aggregations[field_type] = self._create_field_aggregation(
                field_type, field_data, group_by_type=True
            )
        
        return aggregations
    
    def create_document_summary(self, pages: List[PageExtraction]) -> DocumentFieldSummary:
        """
        Create comprehensive summary of document field extractions.
        
        Args:
            pages: List of PageExtraction entities to summarize
            
        Returns:
            DocumentFieldSummary with statistics and aggregations
        """
        if not pages:
            return DocumentFieldSummary(
                total_fields=0,
                unique_field_names=set(),
                total_pages=0,
                field_aggregations=[],
                overall_confidence=0.0,
                fields_needing_review=0
            )
        
        # Collect all fields
        all_fields = []
        unique_field_names = set()
        for page in pages:
            for field in page.fields:
                all_fields.append(field)
                unique_field_names.add(field.field_name)
        
        # Calculate overall statistics
        total_fields = len(all_fields)
        total_pages = len(pages)
        
        # Calculate overall confidence
        if all_fields:
            confidence_sum = sum(field.confidence.value for field in all_fields)
            overall_confidence = confidence_sum / total_fields
        else:
            overall_confidence = 0.0
        
        # Count fields needing review
        fields_needing_review = sum(
            1 for field in all_fields 
            if field.confidence.is_low(self._low_confidence_threshold)
        )
        
        # Create field aggregations
        field_aggregations_dict = self.aggregate_fields_by_name(pages)
        field_aggregations = list(field_aggregations_dict.values())
        
        return DocumentFieldSummary(
            total_fields=total_fields,
            unique_field_names=unique_field_names,
            total_pages=total_pages,
            field_aggregations=field_aggregations,
            overall_confidence=overall_confidence,
            fields_needing_review=fields_needing_review
        )
    
    def find_inconsistent_fields(self, pages: List[PageExtraction]) -> List[FieldAggregation]:
        """
        Find fields that have inconsistent values across pages.
        
        Args:
            pages: List of PageExtraction entities to analyze
            
        Returns:
            List of FieldAggregations where is_consistent is False
        """
        aggregations = self.aggregate_fields_by_name(pages)
        return [agg for agg in aggregations.values() if not agg.is_consistent]
    
    def find_fields_across_pages(
        self, 
        pages: List[PageExtraction], 
        field_name: str
    ) -> List[Tuple[int, FieldExtraction]]:
        """
        Find all instances of a specific field across pages.
        
        Args:
            pages: List of PageExtraction entities to search
            field_name: Name of field to find
            
        Returns:
            List of tuples (page_number, field) for all instances found
        """
        results = []
        for page in pages:
            for field in page.fields:
                if field.field_name == field_name:
                    results.append((page.page_number, field))
        return results
    
    def calculate_field_coverage(self, pages: List[PageExtraction]) -> Dict[str, float]:
        """
        Calculate what percentage of pages each field appears on.
        
        Args:
            pages: List of PageExtraction entities to analyze
            
        Returns:
            Dictionary mapping field names to coverage percentages (0.0-1.0)
        """
        if not pages:
            return {}
        
        total_pages = len(pages)
        field_page_counts = defaultdict(set)
        
        # Track which pages each field appears on
        for page in pages:
            for field in page.fields:
                field_page_counts[field.field_name].add(page.page_number)
        
        # Calculate coverage percentages
        coverage = {}
        for field_name, pages_set in field_page_counts.items():
            coverage[field_name] = len(pages_set) / total_pages
        
        return coverage
    
    def _create_field_aggregation(
        self, 
        key: str, 
        field_data: List[Tuple[FieldExtraction, int]],
        group_by_type: bool = False
    ) -> FieldAggregation:
        """
        Create FieldAggregation from field data.
        
        Args:
            key: Field name or type being aggregated
            field_data: List of (field, page_number) tuples
            group_by_type: Whether grouping by type (vs. name)
            
        Returns:
            FieldAggregation with statistics
        """
        if not field_data:
            return FieldAggregation(
                field_name=key,
                field_type="",
                total_occurrences=0,
                pages_found=set(),
                values=[],
                confidence_scores=[],
                average_confidence=0.0,
                most_common_value=None,
                is_consistent=True
            )
        
        # Extract data
        fields = [field for field, _ in field_data]
        pages = {page_num for _, page_num in field_data}
        values = [field.value for field in fields]
        confidence_scores = [field.confidence.value for field in fields]
        
        # Determine field name and type
        if group_by_type:
            field_name = key  # When grouping by type, use type as name
            field_type = key
        else:
            field_name = key
            field_type = fields[0].field_type if fields else ""
        
        # Calculate statistics
        total_occurrences = len(fields)
        average_confidence = sum(confidence_scores) / total_occurrences if confidence_scores else 0.0
        
        # Find most common value
        value_counts = defaultdict(int)
        for value in values:
            value_counts[value] += 1
        most_common_value = max(value_counts.items(), key=lambda x: x[1])[0] if value_counts else None
        
        # Check consistency (all values are the same)
        unique_values = list(set(values))
        is_consistent = len(unique_values) <= 1
        
        return FieldAggregation(
            field_name=field_name,
            field_type=field_type,
            total_occurrences=total_occurrences,
            pages_found=pages,
            values=unique_values,
            confidence_scores=confidence_scores,
            average_confidence=average_confidence,
            most_common_value=most_common_value,
            is_consistent=is_consistent
        )