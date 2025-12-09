"""
Schemas for job processing and extraction endpoints
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common_schemas import BoundingBoxSchema


class FieldExtractionSchema(BaseModel):
    id: str
    page: int
    name: str
    value: str
    confidence: float
    bbox: Optional[BoundingBoxSchema] = None
    sourceType: Optional[str] = None
    revised: Optional[bool] = False
    originalValue: Optional[str] = None


class TableCellSchema(BaseModel):
    value: str
    confidence: Optional[float] = None
    bbox: Optional[BoundingBoxSchema] = None


class TableColumnSchema(BaseModel):
    key: str
    header: str
    type: Optional[str] = None
    confidence: Optional[float] = None


class TableExtractionSchema(BaseModel):
    id: str
    page: int
    caption: Optional[str] = None
    confidence: Optional[float] = None
    columns: List[TableColumnSchema] = Field(default_factory=list)
    rows: List[List[TableCellSchema]] = Field(default_factory=list)
    bbox: Optional[BoundingBoxSchema] = None
    normalized: Optional[bool] = True
    tableGroupId: Optional[str] = None
    continuationOf: Optional[str] = None
    inferredHeaders: Optional[bool] = False
    rowStartIndex: int = 0


class PageExtractionSchema(BaseModel):
    pageNumber: int
    status: str
    fields: List[FieldExtractionSchema] = Field(default_factory=list)
    tables: List[TableExtractionSchema] = Field(default_factory=list)
    imageUrl: Optional[str] = None
    markdownText: Optional[str] = None
    errorMessage: Optional[str] = None
    rotationApplied: Optional[int] = 0
    documentTypeHint: Optional[str] = None
    documentTypeConfidence: Optional[float] = None


class PageClassificationSchema(BaseModel):
    page: int
    label: Optional[str] = None
    confidence: Optional[float] = None
    reasons: List[str] = Field(default_factory=list)


class JobStatusSchema(BaseModel):
    jobId: str
    totalPages: int
    processedPages: int
    state: str
    errors: List[dict] = Field(default_factory=list)
    startedAt: datetime
    finishedAt: Optional[datetime] = None
    documentType: Optional[str] = None
    documentTypes: List[str] = Field(default_factory=list)


class AggregatedFieldSchema(BaseModel):
    canonicalName: str
    pages: List[int]
    values: List[dict]
    bestValue: str
    confidenceStats: dict


class AggregatedResultsSchema(BaseModel):
    jobId: str
    fields: List[AggregatedFieldSchema]


class CanonicalBundleSchema(BaseModel):
    jobId: str
    canonical: Dict[str, Any]
    trace: Optional[Dict[str, Any]] = None
    documentCategories: List[str] = Field(default_factory=list)
    documentTypes: List[str] = Field(default_factory=list)
    pageCategories: Dict[int, str] = Field(default_factory=dict)
    pageClassifications: List[PageClassificationSchema] = Field(default_factory=list)


class UploadResponseSchema(BaseModel):
    jobId: str


class JobDetailSchema(BaseModel):
    status: JobStatusSchema
    pages: List[PageExtractionSchema]
    aggregated: AggregatedResultsSchema
    documentType: Optional[str] = None
    canonical: Optional[Dict[str, Any]] = None
    mappingTrace: Optional[Dict[str, Any]] = None
    pageClassifications: List[PageClassificationSchema] = Field(default_factory=list)


def page_to_schema(page) -> PageExtractionSchema:
    image_url = None
    if page.image_path and page.image_path.exists():
        # expose relative path handled by static endpoint later if needed
        image_url = f"/api/jobs/{page.page_number}/image"  # placeholder
    return PageExtractionSchema(
        pageNumber=page.page_number,
        status=page.status,
        fields=page.fields,
        tables=page.tables,
        imageUrl=image_url,
        markdownText=getattr(page, "markdown_text", None),
        errorMessage=page.error_message,
        rotationApplied=getattr(page, "rotation_applied", 0),
        documentTypeHint=getattr(page, "document_type_hint", None),
        documentTypeConfidence=getattr(page, "document_type_confidence", None),
    )
