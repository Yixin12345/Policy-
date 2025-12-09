from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BoundingBox:
  x: float
  y: float
  width: float
  height: float


@dataclass
class FieldExtraction:
  id: str
  page: int
  name: str
  value: str
  confidence: float
  bbox: Optional[BoundingBox] = None
  source_type: Optional[str] = None
  revised: bool = False
  original_value: Optional[str] = None


@dataclass
class TableCell:
  value: str
  confidence: Optional[float] = None
  bbox: Optional[BoundingBox] = None


@dataclass
class TableColumn:
  key: str
  header: str
  type: Optional[str] = None
  confidence: Optional[float] = None


@dataclass
class TableExtraction:
  id: str
  page: int
  caption: Optional[str] = None
  confidence: Optional[float] = None
  columns: List[TableColumn] = field(default_factory=list)
  rows: List[List[TableCell]] = field(default_factory=list)
  bbox: Optional[BoundingBox] = None
  normalized: bool = True
  table_group_id: Optional[str] = None
  continuation_of: Optional[str] = None
  inferred_headers: bool = False
  row_start_index: int = 0


@dataclass
class PageExtraction:
  page_number: int
  status: str = "pending"
  image_path: Optional[Path] = None
  image_mime: Optional[str] = None
  markdown_text: Optional[str] = None
  fields: List[FieldExtraction] = field(default_factory=list)
  tables: List[TableExtraction] = field(default_factory=list)
  error_message: Optional[str] = None
  rotation_applied: int = 0
  document_type_hint: Optional[str] = None
  document_type_confidence: Optional[float] = None


@dataclass
class JobStatus:
  job_id: str
  total_pages: int
  processed_pages: int = 0
  state: str = "queued"
  errors: List[Dict[str, Any]] = field(default_factory=list)
  started_at: datetime = field(default_factory=datetime.utcnow)
  finished_at: Optional[datetime] = None


@dataclass
class ExtractionJob:
  status: JobStatus
  pdf_path: Path
  output_dir: Path
  pages: List[PageExtraction]
  aggregated: Dict[str, Any] = field(default_factory=dict)
  metadata: Dict[str, Any] = field(default_factory=dict)
  document_type: Optional[str] = None
  canonical: Optional[Dict[str, Any]] = None
  mapping_trace: Dict[str, Any] = field(default_factory=dict)
