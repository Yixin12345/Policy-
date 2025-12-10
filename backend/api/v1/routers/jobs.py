"""Job-related API routes for v1 endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.api.schemas import JobStatusSchema, PageExtractionSchema
from backend.api.schemas.common_schemas import BoundingBoxSchema
from backend.api.schemas.history_schemas import AggregatedResultsSchema
from backend.api.schemas.job_schemas import (
    CanonicalBundleSchema,
    FieldExtractionSchema,
    PageClassificationSchema,
    TableCellSchema,
    TableColumnSchema,
    TableExtractionSchema,
)
from backend.api.v1.dependencies import (
    get_aggregated_results_handler,
    get_canonical_bundle_handler,
    get_extraction_result_handler,
    get_job_status_handler,
    get_page_repository,
)
from backend.application.dto.job_dto import AggregatedResultsDTO, JobStatusDTO
from backend.application.queries.get_extraction_result import (
    ExtractionResult,
    FormField,
    GetExtractionResultHandler,
    GetExtractionResultQuery,
    TableData,
)
from backend.application.queries.get_aggregated_results import (
    GetAggregatedResultsHandler,
    GetAggregatedResultsQuery,
)
from backend.application.queries.get_canonical_bundle import (
    GetCanonicalBundleHandler,
    GetCanonicalBundleQuery,
)
from backend.application.queries.get_job_status import (
    GetJobStatusHandler,
    GetJobStatusQuery,
)
from backend.domain.exceptions import EntityNotFoundError, RepositoryError
from backend.domain.repositories.page_repository import PageRepository
from backend.legacy.services.history_service import load_job_from_snapshot
from backend.models.job import (
    FieldExtraction as LegacyFieldExtraction,
    TableExtraction as LegacyTableExtraction,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/status", response_model=JobStatusSchema)
def get_job_status(
    job_id: str,
    handler: GetJobStatusHandler = Depends(get_job_status_handler),
) -> JobStatusSchema:
    try:
        dto = handler.handle(GetJobStatusQuery(job_id=job_id))
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail="Failed to load job status") from exc

    return _job_status_to_schema(dto)


@router.get("/{job_id}/pages/{page_number}", response_model=PageExtractionSchema)
def get_page(
    job_id: str,
    page_number: int,
    handler: GetExtractionResultHandler = Depends(get_extraction_result_handler),
    page_repository: PageRepository = Depends(get_page_repository),
) -> PageExtractionSchema:
    try:
        result = handler.handle(
            GetExtractionResultQuery(job_id=job_id, page_number=page_number)
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail="Failed to load page data") from exc

    page_schema = _extraction_result_to_schema(result)

    page_entity = page_repository.find_page(job_id, page_number)
    image_path = None
    if page_entity and getattr(page_entity, "image_path", None):
        image_path = Path(page_entity.image_path)
        if not image_path.exists():
            image_path = None

    if image_path:
        page_schema.imageUrl = f"/api/jobs/{job_id}/pages/{page_number}/image"

    legacy_page = None
    legacy_job = load_job_from_snapshot(job_id)
    if legacy_job:
        legacy_page = next((page for page in legacy_job.pages if page.page_number == page_number), None)

    if legacy_page:
        page_schema.documentTypeHint = legacy_page.document_type_hint
        page_schema.documentTypeConfidence = legacy_page.document_type_confidence
        page_schema.fields = [_legacy_field_to_schema(field, legacy_page.page_number) for field in legacy_page.fields]
        page_schema.tables = [_legacy_table_to_schema(table) for table in legacy_page.tables]
        page_schema.markdownText = getattr(legacy_page, "markdown_text", None)
        if legacy_page.status:
            page_schema.status = legacy_page.status
        if legacy_page.error_message:
            page_schema.errorMessage = legacy_page.error_message

    return page_schema


@router.get("/{job_id}/pages/{page_number}/image")
def get_page_image(
    job_id: str,
    page_number: int,
    page_repository: PageRepository = Depends(get_page_repository),
) -> FileResponse:
    page = page_repository.find_page(job_id, page_number)
    if not page or not getattr(page, "image_path", None):
        raise HTTPException(status_code=404, detail="Page not found")

    image_path = Path(page.image_path)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(image_path)


@router.get("/{job_id}/aggregated", response_model=AggregatedResultsSchema)
def get_aggregated_results(
    job_id: str,
    handler: GetAggregatedResultsHandler = Depends(get_aggregated_results_handler),
) -> AggregatedResultsSchema:
    try:
        dto = handler.handle(GetAggregatedResultsQuery(job_id=job_id))
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail="Failed to load aggregated results") from exc

    return _aggregated_results_to_schema(dto)


@router.get("/{job_id}/canonical", response_model=CanonicalBundleSchema)
def get_canonical_bundle(
    job_id: str,
    handler: GetCanonicalBundleHandler = Depends(get_canonical_bundle_handler),
) -> CanonicalBundleSchema:
    try:
        dto = handler.handle(GetCanonicalBundleQuery(job_id=job_id))
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status_code=500, detail="Failed to load canonical bundle") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    classifications = [PageClassificationSchema(**item) for item in dto.page_classifications]

    return CanonicalBundleSchema(
        jobId=dto.job_id,
        canonical=dto.canonical,
        trace=dto.trace,
        documentCategories=dto.document_categories,
        documentTypes=dto.document_types,
        pageCategories=dto.page_categories,
        pageClassifications=classifications,
    )


def _job_status_to_schema(dto: JobStatusDTO) -> JobStatusSchema:
    errors: List[dict] = []
    if dto.error_message:
        errors = [{"message": dto.error_message}]

    finished_at = dto.updated_at if dto.updated_at != dto.created_at else None

    return JobStatusSchema(
        jobId=dto.job_id,
        totalPages=dto.total_pages or 0,
        processedPages=dto.processed_pages or 0,
        state=dto.status,
        errors=errors,
        startedAt=dto.created_at,
        finishedAt=finished_at,
        documentType=None,
        documentTypes=[],
    )


def _extraction_result_to_schema(result: ExtractionResult) -> PageExtractionSchema:
    fields = [_form_field_to_schema(result, field) for field in result.form_fields]
    tables = [
        _table_to_schema(result, table, index)
        for index, table in enumerate(result.tables)
    ]

    error_message = None
    if result.has_errors and result.error_messages:
        error_message = "; ".join(result.error_messages)

    status = "error" if result.has_errors else "completed"

    return PageExtractionSchema(
        pageNumber=result.page_number,
        status=status,
        fields=fields,
        tables=tables,
        imageUrl=None,
        errorMessage=error_message,
        rotationApplied=0,
        documentTypeHint=None,
        documentTypeConfidence=None,
    )


def _aggregated_results_to_schema(dto: AggregatedResultsDTO) -> AggregatedResultsSchema:
    return AggregatedResultsSchema(
        jobId=dto.job_id,
        fields=[
            {
                "canonicalName": field.canonical_name,
                "pages": field.pages,
                "values": [
                    {
                        "page": value.page,
                        "value": value.value,
                        "confidence": value.confidence,
                    }
                    for value in field.values
                ],
                "bestValue": field.best_value,
                "confidenceStats": field.confidence_stats,
            }
            for field in dto.fields
        ],
    )


def _form_field_to_schema(result: ExtractionResult, field: FormField) -> FieldExtractionSchema:
    bbox = None
    if field.bounding_box:
        bbox = BoundingBoxSchema(**field.bounding_box)

    field_id = f"{result.job_id}-{result.page_number}-{field.name or 'field'}"

    return FieldExtractionSchema(
        id=field_id,
        page=result.page_number,
        name=field.name,
        value=field.value,
        confidence=field.confidence,
        bbox=bbox,
        sourceType=field.field_type,
        revised=False,
        originalValue=None,
    )


def _table_to_schema(result: ExtractionResult, table: TableData, index: int) -> TableExtractionSchema:
    columns: List[TableColumnSchema] = []
    if table.headers:
        for idx, header in enumerate(table.headers):
            columns.append(
                TableColumnSchema(
                    key=f"col_{idx}",
                    header=header,
                )
            )

    rows: List[List[TableCellSchema]] = []
    for row in table.rows:
        row_cells: List[TableCellSchema] = []
        for value in row:
            row_cells.append(TableCellSchema(value=str(value)))
        rows.append(row_cells)

    bbox = BoundingBoxSchema(**table.bounding_box) if table.bounding_box else None

    return TableExtractionSchema(
        id=f"{result.job_id}-{result.page_number}-table-{index}",
        page=result.page_number,
        caption=None,
        confidence=table.confidence,
        columns=columns,
        rows=rows,
        bbox=bbox,
        normalized=True,
        tableGroupId=None,
        continuationOf=None,
        inferredHeaders=False,
        rowStartIndex=0,
    )


def _legacy_bbox_to_schema(bbox) -> Optional[BoundingBoxSchema]:
    if not bbox:
        return None
    return BoundingBoxSchema(x=bbox.x, y=bbox.y, width=bbox.width, height=bbox.height)


def _legacy_field_to_schema(field: LegacyFieldExtraction, page_number: int) -> FieldExtractionSchema:
    bbox = _legacy_bbox_to_schema(field.bbox)
    return FieldExtractionSchema(
        id=field.id,
        page=page_number,
        name=field.name,
        value=field.value,
        confidence=field.confidence,
        bbox=bbox,
        sourceType=field.source_type,
        revised=field.revised,
        originalValue=field.original_value,
    )


def _legacy_table_to_schema(table: LegacyTableExtraction) -> TableExtractionSchema:
    columns: List[TableColumnSchema] = []
    if table.columns:
        for idx, column in enumerate(table.columns):
            key = column.key or f"col_{idx}"
            header = column.header or f"Column {idx + 1}"
            columns.append(
                TableColumnSchema(
                    key=key,
                    header=header,
                    type=column.type,
                    confidence=column.confidence,
                )
            )
    else:
        column_count = max((len(row) for row in table.rows), default=0)
        columns = [
            TableColumnSchema(
                key=f"col_{idx}",
                header=f"Column {idx + 1}",
            )
            for idx in range(column_count)
        ]

    max_columns = len(columns)
    rows: List[List[TableCellSchema]] = []
    for row in table.rows:
        row_cells: List[TableCellSchema] = []
        for col_index in range(max_columns or len(row)):
            if col_index < len(row):
                cell = row[col_index]
                bbox = _legacy_bbox_to_schema(cell.bbox)
                row_cells.append(
                    TableCellSchema(
                        value=cell.value,
                        confidence=cell.confidence,
                        bbox=bbox,
                    )
                )
            else:
                row_cells.append(TableCellSchema(value=""))
        rows.append(row_cells)

    bbox = _legacy_bbox_to_schema(table.bbox)

    return TableExtractionSchema(
        id=table.id,
        page=table.page,
        caption=table.caption,
        confidence=table.confidence,
        columns=columns,
        rows=rows,
        bbox=bbox,
        normalized=table.normalized,
        tableGroupId=table.table_group_id,
        continuationOf=table.continuation_of,
        inferredHeaders=table.inferred_headers,
        rowStartIndex=table.row_start_index,
    )
