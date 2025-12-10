"""Legacy Page entity kept for compatibility with existing query handlers/tests.

The clean architecture refactor introduces ``PageExtraction`` as the primary
page aggregate. Several application-layer queries (and their tests) still
reference a lightweight ``Page`` type with richer OCR metadata. This module
provides that structure so we can bridge both worlds during the migration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Page:
    """Represents historical OCR page data with flexible metadata."""

    job_id: str
    page_number: int
    extracted_text: str = ""
    confidence_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Optional structured payloads used by legacy features/tests
    structured_data: Dict[str, Any] = field(default_factory=dict)
    raw_ocr_data: Optional[Dict[str, Any]] = None
    image_metadata: Optional[Dict[str, Any]] = None
    processing_metadata: Optional[Dict[str, Any]] = None

    # Error reporting
    processing_errors: List[str] = field(default_factory=list)
    processing_warnings: List[str] = field(default_factory=list)
