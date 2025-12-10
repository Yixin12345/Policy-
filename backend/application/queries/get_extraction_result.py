"""
Get Extraction Result Query - Retrieves processed OCR data for a job page

Provides structured access to extraction results including:
- Full text content with confidence scores
- Structured data (tables, forms, etc.)
- Image information and regions
- Processing metadata

Query pattern ensures:
- Clean read-only operations
- Proper data formatting
- Performance optimization
- Error handling for missing data
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from backend.domain.entities.page import Page
from backend.domain.entities.field_extraction import FieldExtraction as DomainField
from backend.domain.entities.page_extraction import PageExtraction as DomainPage
from backend.domain.entities.table_extraction import TableExtraction as DomainTable, TableCell
from backend.domain.exceptions import (
    EntityNotFoundError,
    DomainValidationError,
    RepositoryError
)
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.repositories.page_repository import PageRepository


@dataclass
class GetExtractionResultQuery:
    """Query to get extraction result for a specific job page"""
    job_id: str
    page_number: int
    include_raw_data: bool = False  # Include raw OCR engine response
    include_regions: bool = True    # Include text regions and bounding boxes
    include_metadata: bool = True   # Include processing metadata
    
    def __post_init__(self):
        """Validate query parameters"""
        if not self.job_id or not self.job_id.strip():
            raise DomainValidationError("Job ID cannot be empty")
        
        if self.page_number < 1:
            raise DomainValidationError("Page number must be positive")


@dataclass
class TextRegion:
    """Represents a text region with location and content"""
    text: str
    confidence: float
    bounding_box: Dict[str, float]  # {"x": 0, "y": 0, "width": 100, "height": 20}
    region_type: str  # "paragraph", "line", "word", "character"


@dataclass
class TableData:
    """Represents extracted table data"""
    rows: List[List[str]]
    headers: Optional[List[str]] = None
    confidence: float = 0.0
    bounding_box: Optional[Dict[str, float]] = None


@dataclass
class FormField:
    """Represents extracted form field data"""
    name: str
    value: str
    field_type: str  # "text", "checkbox", "dropdown", etc.
    confidence: float
    bounding_box: Optional[Dict[str, float]] = None


@dataclass
class ExtractionResult:
    """Complete extraction result for a page"""
    job_id: str
    page_number: int
    
    # Core content
    full_text: str
    text_regions: List[TextRegion]
    
    # Structured data
    tables: List[TableData]
    form_fields: List[FormField]
    
    # Image information
    image_width: int
    image_height: int
    processing_timestamp: datetime
    processing_duration_ms: int
    ocr_engine: str
    ocr_engine_version: str
    confidence_score: float

    # Optional image metadata
    image_dpi: Optional[int] = None
    
    # Optional raw data
    raw_ocr_response: Optional[Dict[str, Any]] = None
    
    # Status information
    has_errors: bool = False
    error_messages: List[str] = None
    warnings: List[str] = None


class GetExtractionResultHandler:
    """Handles GetExtractionResult query execution"""
    
    def __init__(
        self,
        job_repository: JobRepository,
        page_repository: PageRepository
    ):
        self._job_repository = job_repository
        self._page_repository = page_repository
        self._logger = logging.getLogger(__name__)
    
    def handle(self, query: GetExtractionResultQuery) -> ExtractionResult:
        """
        Execute extraction result query
        
        Args:
            query: GetExtractionResultQuery with request details
            
        Returns:
            ExtractionResult with extracted data
            
        Raises:
            EntityNotFoundError: If job or page not found
            DomainValidationError: If query parameters invalid
            RepositoryError: If data access fails
        """
        try:
            # 1. Validate job exists
            job = self._job_repository.find_by_id(query.job_id)
            if not job:
                raise EntityNotFoundError("Job", query.job_id, message=f"Job not found: {query.job_id}")

            # 2. Get page data
            page = self._get_page(query.job_id, query.page_number)
            if not page:
                raise EntityNotFoundError(
                    "Page",
                    f"{query.job_id}:{query.page_number}",
                    message=f"Page {query.page_number} not found for job {query.job_id}"
                )

            # 3. Build extraction result
            return self._build_extraction_result(job_id=query.job_id, page=page, query=query)
            
        except (EntityNotFoundError, DomainValidationError):
            # Re-raise domain exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise RepositoryError(
                f"Failed to get extraction result for job {query.job_id}, "
                f"page {query.page_number}: {str(e)}"
            ) from e

    def _get_page(self, job_id: str, page_number: int) -> Optional[Page]:
        """Retrieve page using legacy or current repository method names."""
        legacy_lookup = getattr(self._page_repository, "find_page_by_number", None)
        if callable(legacy_lookup):
            return legacy_lookup(job_id, page_number)
        return self._page_repository.find_page(job_id, page_number)
    
    def _build_extraction_result(
        self,
        job_id: str,
        page,
        query: GetExtractionResultQuery,
    ) -> ExtractionResult:
        """Build ExtractionResult from either legacy or new domain page types."""

        if isinstance(page, DomainPage):
            return self._build_from_domain_page(job_id, page)

        if isinstance(page, Page):
            return self._build_from_legacy_page(page, query)

        raise RepositoryError(f"Unsupported page payload type: {type(page)!r}")

    # ------------------------------------------------------------------
    # Domain (new) page conversion
    # ------------------------------------------------------------------
    def _build_from_domain_page(self, job_id: str, page: DomainPage) -> ExtractionResult:
        form_fields = [
            FormField(
                name=field.field_name,
                value=field.value,
                field_type=field.field_type,
                confidence=field.confidence.value,
                bounding_box=field.bounding_box.to_dict() if field.bounding_box else None,
            )
            for field in page.fields
        ]

        tables = [
            TableData(
                rows=table.to_grid(),
                headers=self._extract_table_headers(table),
                confidence=table.confidence.value if table.confidence else 0.0,
                bounding_box=table.bounding_box.to_dict() if table.bounding_box else None,
            )
            for table in page.tables
        ]

        error_messages = [page.error_message] if getattr(page, "error_message", None) else []

        return ExtractionResult(
            job_id=job_id,
            page_number=page.page_number,
            full_text="",
            text_regions=[],
            tables=tables,
            form_fields=form_fields,
            image_width=0,
            image_height=0,
            processing_timestamp=datetime.utcnow(),
            processing_duration_ms=0,
            ocr_engine="unknown",
            ocr_engine_version="unknown",
            confidence_score=page.overall_confidence.value,
            raw_ocr_response=None,
            has_errors=bool(error_messages),
            error_messages=error_messages,
            warnings=[],
        )

    def _extract_table_headers(self, table: DomainTable) -> Optional[List[str]]:
        headers = [cell.content for cell in table.get_headers()]
        return headers if headers else None

    # ------------------------------------------------------------------
    # Legacy page conversion (existing behaviour)
    # ------------------------------------------------------------------
    def _build_from_legacy_page(
        self,
        page: Page,
        query: GetExtractionResultQuery,
    ) -> ExtractionResult:
        
        # Extract core content
        full_text = page.extracted_text or ""
        text_regions = self._extract_text_regions(page) if query.include_regions else []
        
        # Extract structured data
        tables = self._extract_tables(page)
        form_fields = self._extract_form_fields(page)
        
        # Get image information
        image_info = self._get_image_information(page)
        
        # Get processing metadata
        metadata = self._get_processing_metadata(page) if query.include_metadata else {}
        
        # Get raw data if requested
        raw_data = page.raw_ocr_data if query.include_raw_data else None
        
        # Check for errors and warnings
        errors = page.processing_errors or []
        warnings = page.processing_warnings or []
        
        return ExtractionResult(
            job_id=page.job_id,
            page_number=page.page_number,
            
            # Core content
            full_text=full_text,
            text_regions=text_regions,
            
            # Structured data
            tables=tables,
            form_fields=form_fields,
            
            # Image information
            image_width=image_info.get('width', 0),
            image_height=image_info.get('height', 0),
            image_dpi=image_info.get('dpi'),
            
            # Processing metadata
            processing_timestamp=page.created_at,
            processing_duration_ms=metadata.get('duration_ms', 0),
            ocr_engine=metadata.get('engine', 'unknown'),
            ocr_engine_version=metadata.get('engine_version', 'unknown'),
            confidence_score=page.confidence_score or 0.0,
            
            # Optional raw data
            raw_ocr_response=raw_data,
            
            # Status information
            has_errors=len(errors) > 0,
            error_messages=errors,
            warnings=warnings
        )
    
    def _extract_text_regions(self, page: Page) -> List[TextRegion]:
        """Extract text regions from page data"""
        regions = []
        
        # This depends on how your Page entity stores region data
        # Example assuming page has structured_data with regions
        if hasattr(page, 'structured_data') and page.structured_data:
            region_data = page.structured_data.get('regions', [])
            
            for region in region_data:
                regions.append(TextRegion(
                    text=region.get('text', ''),
                    confidence=region.get('confidence', 0.0),
                    bounding_box=region.get('bbox', {}),
                    region_type=region.get('type', 'paragraph')
                ))
        
        return regions
    
    def _extract_tables(self, page: Page) -> List[TableData]:
        """Extract table data from page"""
        tables = []
        
        # This depends on how your Page entity stores table data
        if hasattr(page, 'structured_data') and page.structured_data:
            table_data = page.structured_data.get('tables', [])
            
            for table in table_data:
                tables.append(TableData(
                    rows=table.get('rows', []),
                    headers=table.get('headers'),
                    confidence=table.get('confidence', 0.0),
                    bounding_box=table.get('bbox')
                ))
        
        return tables
    
    def _extract_form_fields(self, page: Page) -> List[FormField]:
        """Extract form field data from page"""
        form_fields = []
        
        # This depends on how your Page entity stores form data
        if hasattr(page, 'structured_data') and page.structured_data:
            form_data = page.structured_data.get('forms', [])
            
            for field in form_data:
                form_fields.append(FormField(
                    name=field.get('name', ''),
                    value=field.get('value', ''),
                    field_type=field.get('type', 'text'),
                    confidence=field.get('confidence', 0.0),
                    bounding_box=field.get('bbox')
                ))
        
        return form_fields
    
    def _get_image_information(self, page: Page) -> Dict[str, Any]:
        """Get image dimensions and properties"""
        # This depends on how your Page entity stores image info
        if hasattr(page, 'image_metadata') and page.image_metadata:
            return page.image_metadata
        
        # Default values if no image metadata available
        return {
            'width': 0,
            'height': 0,
            'dpi': None
        }
    
    def _get_processing_metadata(self, page: Page) -> Dict[str, Any]:
        """Get processing metadata from page"""
        metadata = {}
        
        if hasattr(page, 'processing_metadata') and page.processing_metadata:
            metadata = page.processing_metadata.copy()
        
        # Add default values for missing metadata
        metadata.setdefault('duration_ms', 0)
        metadata.setdefault('engine', 'unknown')
        metadata.setdefault('engine_version', 'unknown')
        
        return metadata