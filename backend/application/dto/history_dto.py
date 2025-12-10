"""Data Transfer Objects for job history views."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class TimeWindowMetricsDTO:
    """DTO capturing aggregate metrics for a rolling time window."""

    total_jobs: int
    total_pages: int
    total_fields: int
    total_tables: int
    total_processing_ms: Optional[int] = None


@dataclass(frozen=True)
class DashboardMetricsDTO:
    """DTO aggregating metrics for multiple predefined time windows."""

    week: TimeWindowMetricsDTO
    month: TimeWindowMetricsDTO
    year: TimeWindowMetricsDTO


@dataclass(frozen=True)
class HistoryJobSummaryDTO:
    """DTO capturing job summary details for history listings."""

    job_id: str
    document_name: str
    status: str
    total_pages: int
    total_fields: int
    total_tables: int
    low_confidence_count: int
    confidence_buckets: List[int] = field(default_factory=list)
    document_type: Optional[str] = None
    total_processing_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None


@dataclass(frozen=True)
class LowConfidenceFieldDTO:
    """DTO representing a low-confidence field across all jobs."""

    job_id: str
    document_name: str
    page: int
    name: str
    value: str
    confidence: float
