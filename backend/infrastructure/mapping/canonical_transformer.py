"""Transform domain jobs into canonical mapping payloads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.entities.table_extraction import TableCell, TableExtraction
from backend.domain.value_objects.bounding_box import BoundingBox


@dataclass(frozen=True)
class CanonicalPayload:
    """Wrapper for the canonical mapping payload and optional metadata."""

    payload: Dict[str, Any]


class CanonicalTransformer:
    """Builds canonical mapping payloads from domain entities."""

    def build_payload(
        self,
        job: Job,
        *,
        aggregated: Optional[Dict[str, Any]] = None,
        table_groups: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CanonicalPayload:
        payload: Dict[str, Any] = {
            "jobId": job.job_id,
            "documentType": metadata.get("documentType") if metadata else None,
            "documentCategories": (metadata or {}).get("documentCategories", []),
            "originalFilename": metadata.get("originalFilename") if metadata else job.filename,
            "pageCategories": (metadata or {}).get("pageCategories", {}),
            "pages": [self._serialize_page(page) for page in job.pages],
            "aggregated": aggregated or {},
            "tableGroups": table_groups or {},
        }
        return CanonicalPayload(payload=payload)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    def _serialize_page(self, page: PageExtraction) -> Dict[str, Any]:
        page_dict = {
            "pageNumber": page.page_number,
            "fields": [self._serialize_field(field) for field in page.fields],
            "tables": [self._serialize_table(table) for table in page.tables],
            "imagePath": page.image_path,
            "hasEdits": page.has_edits,
        }
        return page_dict

    def _serialize_field(self, field: FieldExtraction) -> Dict[str, Any]:
        return {
            "id": str(field.id),
            "name": field.field_name,
            "value": field.value,
            "confidence": field.confidence.value,
            "bbox": self._serialize_bbox(field.bounding_box),
            "page": field.page_number,
            "fieldType": field.field_type,
            "source": field.source,
            "normalizedValue": field.normalized_value,
        }

    def _serialize_table(self, table: TableExtraction) -> Dict[str, Any]:
        rows = self._build_table_rows(table)
        return {
            "id": str(table.id),
            "page": table.page_number,
            "confidence": table.confidence.value,
            "title": table.title,
            "bbox": self._serialize_bbox(table.bounding_box),
            "rows": rows,
            "numRows": table.num_rows,
            "numColumns": table.num_columns,
        }

    def _build_table_rows(self, table: TableExtraction) -> List[List[Dict[str, Any]]]:
        if table.num_rows == 0 or table.num_columns == 0:
            return []

        grid: List[List[List[TableCell]]] = [
            [[] for _ in range(table.num_columns)] for _ in range(table.num_rows)
        ]

        for cell in table.cells:
            for row in range(cell.row, cell.row + cell.rowspan):
                for column in range(cell.column, cell.column + cell.colspan):
                    grid[row][column].append(cell)

        serialized_rows: List[List[Dict[str, Any]]] = []
        for row_cells in grid:
            serialized_row: List[Dict[str, Any]] = []
            for cell_group in row_cells:
                cell = cell_group[0] if cell_group else None
                serialized_row.append(
                    {
                        "value": cell.content if cell else "",
                        "confidence": cell.confidence.value if cell and cell.confidence else None,
                        "bbox": self._serialize_bbox(cell.bounding_box) if cell else None,
                        "isHeader": cell.is_header if cell else False,
                    }
                )
            serialized_rows.append(serialized_row)
        return serialized_rows

    @staticmethod
    def _serialize_bbox(bbox: Optional[BoundingBox]) -> Optional[Dict[str, Any]]:
        if bbox is None:
            return None
        return {
            "x": bbox.x,
            "y": bbox.y,
            "width": bbox.width,
            "height": bbox.height,
        }
