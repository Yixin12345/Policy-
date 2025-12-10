"""SaveEdits Command - Applies user edits to extracted data.

Responsible for updating field/table values, recalculating confidence, and
persisting changes via repositories. Domain logic lives in entities/value objects.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from backend.domain.repositories.job_repository import JobRepository
from backend.domain.repositories.page_repository import PageRepository
from backend.domain.exceptions import EntityNotFoundError, EntityValidationError
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.table_extraction import TableExtraction, TableCell
from backend.domain.value_objects.confidence import Confidence
from backend.domain.value_objects.bounding_box import BoundingBox


@dataclass(frozen=True)
class FieldEdit:
    page_number: int
    field_name: str
    new_value: str

@dataclass(frozen=True)
class TableCellEdit:
    page_number: int
    row: int
    column: int
    new_value: str

@dataclass(frozen=True)
class SaveEditsCommand:
    job_id: str
    field_edits: List[FieldEdit]
    table_cell_edits: List[TableCellEdit]


class SaveEditsHandler:
    """Handles SaveEdits commands."""

    def __init__(self, job_repository: JobRepository, page_repository: PageRepository):
        self._jobs = job_repository
        self._pages = page_repository

    def handle(self, command: SaveEditsCommand) -> Dict[str, Any]:  # Returns summary
        """Apply edits to pages and persist changes.

        Returns a summary dict (could later become a DTO) with counts.
        """
        job = self._jobs.find_by_id(command.job_id)
        if job is None:
            raise EntityNotFoundError("Job", command.job_id)

        field_edit_count = 0
        table_edit_count = 0

        # Group edits by page for efficiency
        pages_by_number: Dict[int, List[FieldEdit]] = {}
        for fe in command.field_edits:
            pages_by_number.setdefault(fe.page_number, []).append(fe)

        table_edits_by_page: Dict[int, List[TableCellEdit]] = {}
        for te in command.table_cell_edits:
            table_edits_by_page.setdefault(te.page_number, []).append(te)

        # Process each affected page
        for page_number in set(list(pages_by_number.keys()) + list(table_edits_by_page.keys())):
            page = self._pages.find_page(command.job_id, page_number)
            if page is None:
                raise EntityNotFoundError("Page", f"job={command.job_id}, page={page_number}")

            # Apply field edits
            for fe in pages_by_number.get(page_number, []):
                target = page.get_field_by_name(fe.field_name)
                if target is None:
                    raise EntityNotFoundError("FieldExtraction", fe.field_name)
                updated = target.update_value(fe.new_value, new_confidence=1.0)
                page = page.update_field(fe.field_name, updated)
                field_edit_count += 1

            # Apply table cell edits
            for te in table_edits_by_page.get(page_number, []):
                target_table = page.tables[0] if page.tables else None  # Simplification: first table only for now
                if target_table is None:
                    raise EntityNotFoundError("TableExtraction", f"page={page_number}")
                cell = target_table.get_cell(te.row, te.column)
                if cell is None:
                    raise EntityNotFoundError("TableCell", f"r={te.row},c={te.column}")
                updated_table = target_table.update_cell(te.row, te.column, te.new_value)
                # Use title or fallback to index for update_table
                table_title = target_table.title or "table_0"  # Fallback for tables without titles
                page = page.update_table(table_title, updated_table)
                table_edit_count += 1

            # Persist updated page via repository (implicitly updates job snapshot)
            self._pages.save_page(command.job_id, page)

        # Re-fetch job to reflect updates in snapshot
        updated_job = self._jobs.find_by_id(command.job_id)
        return {
            "job_id": command.job_id,
            "field_edits_applied": field_edit_count,
            "table_cell_edits_applied": table_edit_count,
            "pages_modified": len(set(list(pages_by_number.keys()) + list(table_edits_by_page.keys()))),
            "total_pages": updated_job.total_pages if updated_job else None,
        }
