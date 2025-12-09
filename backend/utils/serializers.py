from __future__ import annotations

from dataclasses import asdict
from typing import List

from ..models.job import FieldExtraction, PageExtraction, TableExtraction
from ..api.schemas import FieldExtractionSchema, PageExtractionSchema, TableExtractionSchema


def serialize_field(field: FieldExtraction) -> FieldExtractionSchema:
  data = asdict(field)
  data["sourceType"] = data.pop("source_type", None)
  data["originalValue"] = data.pop("original_value", None)
  return FieldExtractionSchema.model_validate(data)


def serialize_table(table: TableExtraction) -> TableExtractionSchema:
  data = asdict(table)
  data["tableGroupId"] = data.pop("table_group_id", None)
  data["continuationOf"] = data.pop("continuation_of", None)
  data["inferredHeaders"] = data.pop("inferred_headers", False)
  data["rowStartIndex"] = data.pop("row_start_index", 0)
  return TableExtractionSchema.model_validate(data)


def serialize_page(page: PageExtraction, image_url: str | None) -> PageExtractionSchema:
  fields = [serialize_field(field) for field in page.fields]
  tables = [serialize_table(table) for table in page.tables]
  return PageExtractionSchema(
    pageNumber=page.page_number,
    status=page.status,
    fields=fields,
    tables=tables,
    imageUrl=image_url,
    markdownText=page.markdown_text,
    errorMessage=page.error_message,
    rotationApplied=getattr(page, "rotation_applied", 0),
    documentTypeHint=getattr(page, "document_type_hint", None),
    documentTypeConfidence=getattr(page, "document_type_confidence", None),
  )
