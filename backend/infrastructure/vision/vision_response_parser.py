"""Parse Azure OpenAI vision responses into domain entities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from backend.constants import CONFIDENCE_STEPS
from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.table_extraction import TableCell, TableExtraction
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.value_objects.bounding_box import BoundingBox
from backend.domain.value_objects.confidence import Confidence

DEFAULT_SOURCE = "azure-openai-vision"


@dataclass
class VisionPageMetadata:
    """Optional metadata produced during parsing."""

    document_type_label: Optional[str] = None
    document_type_confidence: Optional[float] = None
    document_type_reasons: Optional[List[str]] = None


class VisionResponseParser:
    """Converts raw vision payloads into domain page extractions."""

    def parse_page(
        self,
        page_number: int,
        payload: Dict[str, Any],
        *,
        image_path: Optional[str] = None,
        source: str = DEFAULT_SOURCE,
    ) -> PageExtraction:
        metadata = self._parse_document_type(payload)
        fields = tuple(self._parse_fields(page_number, payload.get("fields") or [], source=source))
        tables = tuple(self._parse_tables(page_number, payload.get("tables") or [], source=source))

        page = PageExtraction.create(
            page_number=page_number,
            fields=list(fields),
            tables=list(tables),
            image_path=image_path,
        )

        # Attach metadata if present by updating the dict representation.
        page_dict = page.to_dict()
        if metadata.document_type_label:
            page_dict["document_type_hint"] = metadata.document_type_label
        if metadata.document_type_confidence is not None:
            page_dict["document_type_confidence"] = metadata.document_type_confidence
        if metadata.document_type_reasons:
            page_dict["document_type_reasons"] = metadata.document_type_reasons

        return PageExtraction.from_dict(page_dict)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _parse_document_type(self, payload: Dict[str, Any]) -> VisionPageMetadata:
        document_type = payload.get("documentType")
        if not isinstance(document_type, dict):
            return VisionPageMetadata()

        label = _safe_str(document_type.get("label"))
        confidence = _safe_float(document_type.get("confidence"))
        reasons = document_type.get("reasons")
        if isinstance(reasons, list):
            reasons = [_safe_str(reason) for reason in reasons if reason is not None]
        else:
            reasons = None

        return VisionPageMetadata(
            document_type_label=label or None,
            document_type_confidence=_quantize_confidence(confidence) if confidence is not None else None,
            document_type_reasons=reasons,
        )

    def _parse_fields(
        self,
        page_number: int,
        field_payload: Iterable[Any],
        *,
        source: str,
    ) -> Iterable[FieldExtraction]:
        for index, item in enumerate(field_payload):
            if not isinstance(item, dict):
                continue

            bbox = _parse_bbox(item.get("bbox"))
            confidence = _quantize_confidence(_safe_float(item.get("confidence"))) or 0.0
            field_name = _safe_str(item.get("name")) or f"Field {index + 1}"
            field_value = _safe_str(item.get("value"))
            field_type = _safe_str(item.get("type")) or "text"

            yield FieldExtraction.create(
                field_name=field_name,
                value=field_value,
                field_type=field_type,
                confidence=confidence,
                bounding_box=bbox,
                page_number=page_number,
                source=source,
            )

    def _parse_tables(
        self,
        page_number: int,
        table_payload: Iterable[Any],
        *,
        source: str,
    ) -> Iterable[TableExtraction]:
        for index, item in enumerate(table_payload):
            if not isinstance(item, dict):
                continue

            confidence = _quantize_confidence(_safe_float(item.get("confidence"))) or 0.0
            bbox = _parse_bbox(item.get("bbox"))
            title = _safe_str(item.get("caption")) or None

            rows = item.get("rows") or []
            columns = self._normalize_columns(item.get("columns"))
            cells: List[TableCell] = []

            for row_index, row_payload in enumerate(rows):
                if isinstance(row_payload, list):
                    for column_index, cell_payload in enumerate(row_payload):
                        cells.append(self._parse_cell(row_index, column_index, cell_payload))
                elif isinstance(row_payload, dict):
                    for column_index, column_key in enumerate(columns):
                        cell_payload = row_payload.get(column_key, row_payload.get(column_key.lower()))
                        cells.append(self._parse_cell(row_index, column_index, cell_payload))
                elif row_payload is None:
                    continue
                else:
                    cells.append(
                        TableCell(
                            row=row_index,
                            column=0,
                            content=_safe_str(row_payload),
                            confidence=Confidence(confidence),
                        )
                    )

            yield TableExtraction.create(
                cells=cells,
                page_number=page_number,
                confidence=confidence,
                bounding_box=bbox,
                title=title,
            )

    def _parse_cell(self, row: int, column: int, payload: Any) -> TableCell:
        if isinstance(payload, dict):
            value = payload.get("value")
            if value is None:
                value = payload.get("text") or payload.get("content")
            if isinstance(value, list):
                value = ", ".join(_safe_str(item) for item in value if item is not None)
            bbox = _parse_bbox(payload.get("bbox"))
            confidence = _quantize_confidence(_safe_float(payload.get("confidence")))
            return TableCell(
                row=row,
                column=column,
                content=_safe_str(value),
                confidence=Confidence(confidence) if confidence is not None else None,
                bounding_box=bbox,
            )

        if isinstance(payload, list):
            value = ", ".join(_safe_str(item) for item in payload if item is not None)
            return TableCell(row=row, column=column, content=value)

        if payload is None:
            return TableCell(row=row, column=column, content="")

        return TableCell(row=row, column=column, content=_safe_str(payload))

    def _normalize_columns(self, payload: Any) -> List[str]:
        if isinstance(payload, list):
            normalized: List[str] = []
            for column in payload:
                if isinstance(column, dict):
                    header = _safe_str(column.get("header") or column.get("name") or column.get("key"))
                    normalized.append(header or f"column_{len(normalized)}")
                elif column is None:
                    normalized.append(f"column_{len(normalized)}")
                else:
                    normalized.append(_safe_str(column))
            return normalized
        return []


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _parse_bbox(data: Any) -> Optional[BoundingBox]:
    if not isinstance(data, dict):
        return None
    try:
        return BoundingBox(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            width=float(data.get("width", 0.0)),
            height=float(data.get("height", 0.0)),
        )
    except (TypeError, ValueError):
        return None


def _quantize_confidence(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    clamped = max(0.0, min(1.0, value))
    return min(CONFIDENCE_STEPS, key=lambda step: abs(step - clamped))
