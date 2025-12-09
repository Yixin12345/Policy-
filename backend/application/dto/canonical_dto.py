"""Data transfer objects for canonical mapping responses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CanonicalBundleDTO:
    """Canonical mapping payload returned to the API layer."""

    job_id: str
    canonical: Dict[str, Any]
    trace: Optional[Dict[str, Any]]
    document_categories: List[str]
    document_types: List[str]
    page_categories: Dict[int, str]
    page_classifications: List[Dict[str, Any]]


__all__ = ["CanonicalBundleDTO"]
