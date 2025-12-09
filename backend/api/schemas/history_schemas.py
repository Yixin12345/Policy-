"""
Schemas for job history and metrics endpoints
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .job_schemas import (
    AggregatedResultsSchema,
    FieldExtractionSchema,
    JobStatusSchema,
    PageClassificationSchema,
    PageExtractionSchema,
    TableExtractionSchema,
)


class JobSummaryMetricsSchema(BaseModel):
    totalPages: int
    totalFields: int
    totalTables: int
    totalProcessingMs: Optional[int] = None
    startedAt: Optional[datetime] = None
    finishedAt: Optional[datetime] = None


class JobHistorySummarySchema(BaseModel):
    jobId: str
    documentName: str
    documentType: Optional[str] = None
    totalPages: int
    totalFields: int
    totalTables: int
    totalProcessingMs: Optional[int] = None
    startedAt: Optional[datetime] = None
    finishedAt: Optional[datetime] = None
    lastModified: Optional[datetime] = None
    status: str
    confidenceBuckets: List[int] = Field(default_factory=list)
    lowConfidenceCount: int = 0


class FieldUpdateSchema(BaseModel):
    fieldId: Optional[str] = None
    name: str
    value: str
    confidence: Optional[float] = None


class TableCellUpdateSchema(BaseModel):
    tableId: str
    row: int
    column: int
    value: str


class SaveEditsRequestSchema(BaseModel):
    page: int
    fields: List[FieldUpdateSchema] = Field(default_factory=list)
    tableCells: List[TableCellUpdateSchema] = Field(default_factory=list)


class SaveEditsResponseSchema(BaseModel):
    jobId: str
    page: int
    updatedFields: List[FieldExtractionSchema]
    updatedTables: List[TableExtractionSchema]


class JobHistoryListResponseSchema(BaseModel):
    jobs: List[JobHistorySummarySchema]


class JobHistoryDetailSchema(BaseModel):
    jobId: str
    documentName: str
    summary: JobSummaryMetricsSchema
    status: JobStatusSchema
    pages: List[PageExtractionSchema]
    aggregated: AggregatedResultsSchema
    metadata: Dict[str, Any] = Field(default_factory=dict)
    documentType: Optional[str] = None
    canonical: Optional[Dict[str, Any]] = None
    mappingTrace: Optional[Dict[str, Any]] = None
    pageClassifications: List[PageClassificationSchema] = Field(default_factory=list)


class TimeWindowMetricsSchema(BaseModel):
    totalJobs: int
    totalPages: int
    totalFields: int
    totalTables: int
    totalProcessingMs: Optional[int] = None


class DashboardMetricsResponseSchema(BaseModel):
    week: TimeWindowMetricsSchema
    month: TimeWindowMetricsSchema
    year: TimeWindowMetricsSchema


class LowConfidenceFieldSchema(BaseModel):
    jobId: str
    documentName: str
    page: int
    name: str
    value: str
    confidence: float
