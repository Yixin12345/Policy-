"""
API Schemas - organized by domain
"""
from .common_schemas import BoundingBoxSchema
from .job_schemas import (
    AggregatedFieldSchema,
    AggregatedResultsSchema,
    CanonicalBundleSchema,
    FieldExtractionSchema,
    JobDetailSchema,
    JobStatusSchema,
    PageClassificationSchema,
    PageExtractionSchema,
    TableCellSchema,
    TableColumnSchema,
    TableExtractionSchema,
    UploadResponseSchema,
    page_to_schema,
)
from .history_schemas import (
    DashboardMetricsResponseSchema,
    FieldUpdateSchema,
    JobHistoryDetailSchema,
    JobHistoryListResponseSchema,
    JobHistorySummarySchema,
    JobSummaryMetricsSchema,
    LowConfidenceFieldSchema,
    SaveEditsRequestSchema,
    SaveEditsResponseSchema,
    TableCellUpdateSchema,
    TimeWindowMetricsSchema,
)

__all__ = [
    # Common
    "BoundingBoxSchema",
    # Job schemas
    "FieldExtractionSchema",
    "TableCellSchema",
    "TableColumnSchema",
    "TableExtractionSchema",
    "PageExtractionSchema",
    "PageClassificationSchema",
    "JobStatusSchema",
    "AggregatedFieldSchema",
    "AggregatedResultsSchema",
    "CanonicalBundleSchema",
    "UploadResponseSchema",
    "JobDetailSchema",
    "page_to_schema",
    # History schemas
    "JobSummaryMetricsSchema",
    "JobHistorySummarySchema",
    "FieldUpdateSchema",
    "TableCellUpdateSchema",
    "SaveEditsRequestSchema",
    "SaveEditsResponseSchema",
    "JobHistoryListResponseSchema",
    "JobHistoryDetailSchema",
    "TimeWindowMetricsSchema",
    "DashboardMetricsResponseSchema",
    "LowConfidenceFieldSchema",
]
