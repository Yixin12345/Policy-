"""Data Transfer Objects for Job-related queries."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class JobSummaryDTO:
    """Lightweight DTO for job list/summary views."""

    job_id: str
    status: str
    filename: Optional[str]
    created_at: datetime
    updated_at: datetime
    page_count: int
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "filename": self.filename,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "page_count": self.page_count,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class JobDetailDTO:
    """Detailed DTO for single job view with full extraction data."""

    job_id: str
    status: str
    filename: Optional[str]
    created_at: datetime
    updated_at: datetime
    page_count: int
    progress: float
    error_message: Optional[str] = None
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "filename": self.filename,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "page_count": self.page_count,
            "progress": self.progress,
            "error_message": self.error_message,
            "metadata": self.metadata or {},
        }
