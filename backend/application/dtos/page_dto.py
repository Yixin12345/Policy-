"""Data Transfer Objects for Page-related queries."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PageDataDTO:
    """DTO for page extraction data."""

    job_id: str
    page_number: int
    fields: list[dict]
    tables: list[dict]
    image_path: Optional[str] = None
    has_edits: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "job_id": self.job_id,
            "page_number": self.page_number,
            "fields": self.fields,
            "tables": self.tables,
            "image_path": self.image_path,
            "has_edits": self.has_edits,
        }
