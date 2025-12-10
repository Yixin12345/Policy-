"""
GetPageData Query - Retrieves extraction data for a specific page.

This query fetches field and table extractions for a single page
within a job.
"""
from dataclasses import dataclass
from typing import List

from backend.domain.repositories.page_repository import PageRepository
from backend.domain.exceptions import EntityNotFoundError
from backend.application.dto.page_dto import PageDataDTO, FieldDTO, TableDTO, TableCellDTO


@dataclass(frozen=True)
class GetPageDataQuery:
    """Query to get extraction data for a specific page."""
    
    job_id: str
    page_number: int


class GetPageDataHandler:
    """Handles GetPageData queries."""
    
    def __init__(self, page_repository: PageRepository):
        """
        Initialize handler with repository dependency.
        
        Args:
            page_repository: Repository for accessing page data
        """
        self._page_repository = page_repository
    
    def handle(self, query: GetPageDataQuery) -> PageDataDTO:
        """
        Execute the query and return page data.
        
        Args:
            query: The GetPageData query
            
        Returns:
            PageDataDTO with field and table extractions
            
        Raises:
            EntityNotFoundError: If page not found
        """
        # Find page using repository
        page = self._page_repository.find_page(query.job_id, query.page_number)
        
        if page is None:
            raise EntityNotFoundError(
                "Page",
                f"job={query.job_id}, page={query.page_number}"
            )
        
        # Convert fields to DTOs
        field_dtos: List[FieldDTO] = []
        for field in page.fields:
            bbox_dict = None
            if field.bounding_box is not None:
                bbox_dict = field.bounding_box.to_dict()
            
            field_dtos.append(FieldDTO(
                name=field.field_name,
                value=field.value,
                confidence=field.confidence.value,
                bbox=bbox_dict,
                was_edited=field.was_edited,
            ))
        
        # Convert tables to DTOs
        table_dtos: List[TableDTO] = []
        for table in page.tables:
            cell_dtos: List[TableCellDTO] = []
            for cell in table.cells:
                cell_dtos.append(TableCellDTO(
                    row=cell.row,
                    col=cell.column,
                    value=cell.content,
                    confidence=cell.confidence.value if cell.confidence else 0.0,
                    row_span=cell.rowspan,
                    col_span=cell.colspan,
                ))
            
            bbox_dict = None
            if table.bounding_box is not None:
                bbox_dict = table.bounding_box.to_dict()
            
            table_dtos.append(TableDTO(
                title=table.title,
                cells=cell_dtos,
                bbox=bbox_dict,
            ))
        
        # Build and return DTO
        return PageDataDTO(
            job_id=query.job_id,
            page_number=page.page_number,
            fields=field_dtos,
            tables=table_dtos,
            overall_confidence=page.overall_confidence.value,
            needs_review=page.needs_review(),
        )
