"""
Data Transfer Objects for Job-related queries and commands.

These DTOs serve as the boundary between the application layer and external layers (API, UI).
They are simple, serializable data structures without business logic.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass(frozen=True)
class JobStatusDTO:
    """DTO for job status information."""
    
    job_id: str
    status: str
    progress: float
    filename: str
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    total_pages: Optional[int] = None
    processed_pages: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobStatusDTO":
        """Create DTO from dictionary."""
        return cls(
            job_id=data["job_id"],
            status=data["status"],
            progress=data["progress"],
            filename=data["filename"],
            created_at=data["created_at"] if isinstance(data["created_at"], datetime) else datetime.fromisoformat(data["created_at"]),
            updated_at=data["updated_at"] if isinstance(data["updated_at"], datetime) else datetime.fromisoformat(data["updated_at"]),
            error_message=data.get("error_message"),
            total_pages=data.get("total_pages"),
            processed_pages=data.get("processed_pages"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "filename": self.filename,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "total_pages": self.total_pages,
            "processed_pages": self.processed_pages,
        }


@dataclass(frozen=True)
class JobListItemDTO:
    """DTO for job list item (summary view)."""
    
    job_id: str
    status: str
    filename: str
    created_at: datetime
    progress: float
    total_pages: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobListItemDTO":
        """Create DTO from dictionary."""
        return cls(
            job_id=data["job_id"],
            status=data["status"],
            filename=data["filename"],
            created_at=data["created_at"] if isinstance(data["created_at"], datetime) else datetime.fromisoformat(data["created_at"]),
            progress=data["progress"],
            total_pages=data.get("total_pages"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "filename": self.filename,
            "created_at": self.created_at.isoformat(),
            "progress": self.progress,
            "total_pages": self.total_pages,
        }


@dataclass(frozen=True)
class JobsListDTO:
    """DTO for paginated list of jobs."""
    
    jobs: List[JobListItemDTO]
    total: int
    page: int
    page_size: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DTO to dictionary."""
        return {
            "jobs": [job.to_dict() for job in self.jobs],
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
        }


@dataclass(frozen=True)
class AggregatedFieldValueDTO:
    """DTO representing a single value contributing to an aggregated field."""

    page: int
    value: str
    confidence: float


@dataclass(frozen=True)
class AggregatedFieldDTO:
    """DTO for aggregated field summaries across job pages."""

    canonical_name: str
    pages: List[int]
    values: List[AggregatedFieldValueDTO]
    best_value: str
    confidence_stats: Dict[str, float]


@dataclass(frozen=True)
class AggregatedResultsDTO:
    """DTO for aggregated job results payload."""

    job_id: str
    fields: List[AggregatedFieldDTO]
