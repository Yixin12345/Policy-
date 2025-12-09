from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ...models.job import (
  BoundingBox,
  ExtractionJob,
  FieldExtraction,
  JobStatus,
  PageExtraction,
  TableCell,
  TableColumn,
  TableExtraction,
)
from .aggregation import aggregate_fields
from .store import job_store
from ...constants import SNAPSHOT_VERSION
from ...repositories.snapshot_repository import save_snapshot_payload, load_snapshot as load_snapshot_repo, list_snapshot_raw
from ...config import get_settings

logger = logging.getLogger(__name__)

BASE_STORAGE_DIR = Path("backend_data")
SNAPSHOT_FILENAME = "job_snapshot.json"
CONFIDENCE_BUCKET_BOUNDS: Tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 1.0)
CONFIDENCE_BUCKET_COUNT = len(CONFIDENCE_BUCKET_BOUNDS) + 1
LOW_CONF_THRESHOLD = get_settings().confidence_low_threshold
TERMINAL_STATES = {"completed", "partial", "error"}


def _ensure_storage_dir() -> None:
  BASE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _job_dir(job_id: str) -> Path:
  return BASE_STORAGE_DIR / job_id


def _snapshot_path(job_id: str) -> Path:
  return _job_dir(job_id) / SNAPSHOT_FILENAME


def _normalise_confidence(value: Any) -> float:
  try:
    return float(value)
  except (TypeError, ValueError):
    return 0.0


def _clamp_confidence(value: float) -> float:
  if value < 0.0:
    return 0.0
  if value > 1.0:
    return 1.0
  return value


def _confidence_bucket_index(confidence: float) -> int:
  for index, bound in enumerate(CONFIDENCE_BUCKET_BOUNDS):
    if confidence <= bound:
      return index
  return CONFIDENCE_BUCKET_COUNT - 1


def _compute_confidence_stats_for_job(job: ExtractionJob) -> Tuple[List[int], int]:
  buckets = [0 for _ in range(CONFIDENCE_BUCKET_COUNT)]
  low_confidence_count = 0
  for page in job.pages:
    for field in page.fields:
      confidence = _clamp_confidence(_normalise_confidence(getattr(field, "confidence", 0.0)))
      bucket_index = _confidence_bucket_index(confidence)
      buckets[bucket_index] += 1
      if confidence <= LOW_CONF_THRESHOLD:
        low_confidence_count += 1
  return buckets, low_confidence_count


def _compute_confidence_stats_from_page_dicts(pages: Sequence[Dict[str, Any]]) -> Tuple[List[int], int]:
  buckets = [0 for _ in range(CONFIDENCE_BUCKET_COUNT)]
  low_confidence_count = 0
  for page in pages:
    for field in page.get("fields", []):
      confidence = _clamp_confidence(_normalise_confidence(field.get("confidence", 0.0)))
      bucket_index = _confidence_bucket_index(confidence)
      buckets[bucket_index] += 1
      if confidence <= LOW_CONF_THRESHOLD:
        low_confidence_count += 1
  return buckets, low_confidence_count


def save_job_snapshot(job: ExtractionJob) -> None:  # compatibility shim
  summary = _job_summary(job)
  payload = {
    "jobId": job.status.job_id,
    "documentName": job.metadata.get("originalFilename", job.pdf_path.name),
    "sourcePdf": str(job.pdf_path.name),
    "status": _status_to_dict(job.status),
    "pages": [_page_to_dict(page, job.output_dir) for page in job.pages],
    "aggregated": job.aggregated,
    "metadata": job.metadata,
    "documentType": job.document_type,
    "canonical": job.canonical,
    "mappingTrace": job.mapping_trace,
    "summary": summary,
    "lastModified": datetime.utcnow().isoformat(),
    "snapshotVersion": SNAPSHOT_VERSION,
  }
  save_snapshot_payload(job.status.job_id, payload)


def _coerce_error_list(value: Any) -> List[Dict[str, Any]]:
  if not value:
    return []
  if isinstance(value, list):
    errors: List[Dict[str, Any]] = []
    for item in value:
      if isinstance(item, dict):
        errors.append(item)
      else:
        errors.append({"message": str(item)})
    return errors
  if isinstance(value, dict):
    return [value]
  return [{"message": str(value)}]


def _status_from_snapshot(data: Dict[str, Any], job_id: str) -> JobStatus:
  status_payload = data.get("status")
  if isinstance(status_payload, dict):
    status_job_id = status_payload.get("jobId") or status_payload.get("job_id") or data.get("jobId") or job_id
    total_pages = int(status_payload.get("totalPages", status_payload.get("total_pages", data.get("totalPages", data.get("total_pages", 0)))))
    processed_pages = int(status_payload.get("processedPages", status_payload.get("processed_pages", data.get("processedPages", data.get("processed_pages", total_pages)))))
    state = status_payload.get("state") or status_payload.get("status") or data.get("state") or "completed"
    started_at = _parse_datetime(status_payload.get("startedAt") or status_payload.get("started_at") or data.get("startedAt") or data.get("started_at")) or datetime.utcnow()
    finished_at = _parse_datetime(status_payload.get("finishedAt") or status_payload.get("finished_at") or data.get("finishedAt") or data.get("finished_at"))
    errors = _coerce_error_list(status_payload.get("errors") or data.get("errors"))
    return JobStatus(
      job_id=status_job_id,
      total_pages=total_pages,
      processed_pages=processed_pages,
      state=str(state),
      errors=errors,
      started_at=started_at,
      finished_at=finished_at,
    )

  total_pages = int(data.get("totalPages") or data.get("total_pages") or len(data.get("pages") or []))
  processed_pages = int(data.get("processedPages") or data.get("processed_pages") or total_pages)
  state = status_payload or data.get("state") or "completed"
  started_at = _parse_datetime(data.get("startedAt") or data.get("started_at") or data.get("created_at")) or datetime.utcnow()
  finished_at = _parse_datetime(data.get("finishedAt") or data.get("finished_at") or data.get("completed_at"))
  errors = data.get("errors")
  if not errors and data.get("error_message"):
    errors = [{"message": data.get("error_message")}]
  errors_list = _coerce_error_list(errors)
  return JobStatus(
    job_id=data.get("jobId") or data.get("job_id") or job_id,
    total_pages=total_pages,
    processed_pages=processed_pages,
    state=str(state),
    errors=errors_list,
    started_at=started_at,
    finished_at=finished_at,
  )


def load_job_from_snapshot(job_id: str) -> Optional[ExtractionJob]:
  data = load_snapshot_repo(job_id)
  if not data:
    return None

  try:
    status = _status_from_snapshot(data, job_id)

    job_dir = _job_dir(job_id)
    pages = [_page_from_dict(page_data, job_dir) for page_data in data.get("pages", [])]

    job = ExtractionJob(
      status=status,
      pdf_path=job_dir / (data.get("sourcePdf") or data.get("source_pdf") or data.get("filename") or "source.pdf"),
      output_dir=job_dir,
      pages=pages,
      aggregated=data.get("aggregated") or data.get("aggregated_data") or {},
      metadata=data.get("metadata") or data.get("job_metadata") or {},
      document_type=data.get("documentType") or data.get("document_type"),
      canonical=data.get("canonical"),
      mapping_trace=data.get("mappingTrace") or data.get("mapping_trace") or {},
    )
    return job
  except Exception as exc:  # pragma: no cover - defensive
    logger.exception("Failed to load job snapshot for %s: %s", job_id, exc)
    return None


def list_job_summaries() -> List[Dict[str, Any]]:
  """Return dashboard summaries for all known jobs."""
  _ensure_storage_dir()
  summaries_by_id: Dict[str, Dict[str, Any]] = {}

  for data in list_snapshot_raw():
    try:
      job_id = data.get("jobId")
      summary = data.get("summary") or _job_summary_from_snapshot(data)
      status_state = (data.get("status") or {}).get("state", "completed")
      started_at = _parse_datetime(summary.get("startedAt"))
      finished_at = _parse_datetime(summary.get("finishedAt"))
      job_dir = _job_dir(job_id) if job_id else None
      last_modified = None
      if job_dir and job_dir.exists():
        snapshot_path = job_dir / SNAPSHOT_FILENAME
        if snapshot_path.exists():
          last_modified = datetime.fromtimestamp(snapshot_path.stat().st_mtime, tz=timezone.utc)
      summaries_by_id[data.get("jobId", job_id or "unknown")] = {
        "jobId": data.get("jobId", job_id or "unknown"),
        "documentName": data.get("documentName", "Unknown"),
        "documentType": data.get("documentType"),
        "totalPages": summary.get("totalPages", 0),
        "totalFields": summary.get("totalFields", 0),
        "totalTables": summary.get("totalTables", 0),
        "totalProcessingMs": summary.get("totalProcessingMs"),
        "startedAt": started_at,
        "finishedAt": finished_at,
        "lastModified": last_modified,
        "status": status_state,
        "confidenceBuckets": summary.get("confidenceBuckets", [0] * CONFIDENCE_BUCKET_COUNT),
        "lowConfidenceCount": summary.get("lowConfidenceCount", 0),
      }
    except Exception as exc:  # pragma: no cover
      logger.debug("Skipping snapshot record due to error: %s", exc)

  for job in job_store.list():
    summary = _job_summary(job)
    started_at = _parse_datetime(summary.get("startedAt")) or _ensure_timezone(job.status.started_at)
    finished_at = _parse_datetime(summary.get("finishedAt")) or _ensure_timezone(job.status.finished_at)
    last_modified = finished_at or started_at or datetime.utcnow().replace(tzinfo=timezone.utc)
    summaries_by_id[job.status.job_id] = {
      "jobId": job.status.job_id,
      "documentName": job.metadata.get("originalFilename", job.pdf_path.name),
      "documentType": job.document_type,
      "totalPages": summary.get("totalPages", len(job.pages)),
      "totalFields": summary.get("totalFields", 0),
      "totalTables": summary.get("totalTables", 0),
      "totalProcessingMs": summary.get("totalProcessingMs"),
      "startedAt": started_at,
      "finishedAt": finished_at,
      "lastModified": last_modified,
      "status": job.status.state,
      "confidenceBuckets": summary.get("confidenceBuckets", [0] * CONFIDENCE_BUCKET_COUNT),
      "lowConfidenceCount": summary.get("lowConfidenceCount", 0),
    }

  summaries = list(summaries_by_id.values())
  summaries.sort(
    key=lambda item: (
      item.get("finishedAt")
      or item.get("lastModified")
      or datetime.min.replace(tzinfo=timezone.utc)
    ),
    reverse=True,
  )
  return summaries


def get_low_confidence_fields(limit: int = 50, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
  """Return fields whose confidence is at or below the configured low-confidence threshold."""
  results: List[Dict[str, Any]] = []
  seen_jobs: set[str] = set()

  for job in job_store.list():
    if job_id and job.status.job_id != job_id:
      continue
    seen_jobs.add(job.status.job_id)
    document_name = job.metadata.get("originalFilename", job.pdf_path.name)
    for page in job.pages:
      for field in page.fields:
        confidence = _clamp_confidence(_normalise_confidence(getattr(field, "confidence", 0.0)))
        if confidence <= LOW_CONF_THRESHOLD:
          results.append(
            {
              "jobId": job.status.job_id,
              "documentName": document_name,
              "page": page.page_number,
              "name": getattr(field, "name", ""),
              "value": getattr(field, "value", ""),
              "confidence": confidence,
            }
          )

  if job_id and job_id in seen_jobs:
    matching_jobs = {job_id}
  else:
    matching_jobs = None

  # Fallback to snapshots if the job is not currently in memory (optional for legacy snapshots)
  for job_dir in BASE_STORAGE_DIR.iterdir():
    if not job_dir.is_dir():
      continue
    job_identifier = job_dir.name
    if job_identifier in seen_jobs:
      continue
    if matching_jobs and job_identifier not in matching_jobs:
      continue
    snapshot_path = job_dir / SNAPSHOT_FILENAME
    if not snapshot_path.exists():
      continue
    try:
      data = json.loads(snapshot_path.read_text(encoding="utf-8"))
      document_name = data.get("documentName", "Unknown")
      pages = data.get("pages", [])
      for page in pages:
        page_number = page.get("pageNumber", 0)
        for field in page.get("fields", []):
          confidence = _clamp_confidence(_normalise_confidence(field.get("confidence", 0.0)))
          if confidence <= LOW_CONF_THRESHOLD:
            results.append(
              {
                "jobId": data.get("jobId", job_identifier),
                "documentName": document_name,
                "page": page_number,
                "name": field.get("name", ""),
                "value": field.get("value", ""),
                "confidence": confidence,
              }
            )
    except Exception as exc:  # pragma: no cover - defensive parsing
      logger.debug("Skipping low confidence extraction for %s: %s", snapshot_path, exc)

  results.sort(key=lambda item: (item["confidence"], item["jobId"], item["page"], item["name"]))
  if limit and limit > 0:
    return results[:limit]
  return results


def apply_page_edits(
  job_id: str,
  page_number: int,
  field_updates: Sequence[Dict[str, Any]],
  table_updates: Sequence[Dict[str, Any]],
) -> Tuple[List[FieldExtraction], List[TableExtraction]]:
  """Apply field and table edits to a snapshot and persist the updated job."""
  job = job_store.get(job_id)
  if not job:
    job = load_job_from_snapshot(job_id)
    if not job:
      raise ValueError(f"Job {job_id} not found")
    job_store.add(job)

  if page_number < 1 or page_number > len(job.pages):
    raise ValueError(f"Page {page_number} not found for job {job_id}")

  page = job.pages[page_number - 1]

  updated_fields: List[FieldExtraction] = []
  seen_field_ids: set[str] = set()
  if field_updates:
    for update in field_updates:
      field: Optional[FieldExtraction] = None
      field_id = update.get("fieldId")
      if field_id:
        field = next((item for item in page.fields if item.id == field_id), None)
      if not field:
        name = update.get("name")
        field = next((item for item in page.fields if item.name == name), None)
      if not field:
        identifier = field_id or update.get("name") or "unknown"
        raise ValueError(f"Field {identifier} not found for update")

      new_value = update.get("value", field.value)
      if new_value != field.value:
        if field.revised and field.original_value is not None and new_value == field.original_value:
          field.value = new_value
          field.revised = False
          field.original_value = None
        else:
          if not field.revised:
            field.original_value = field.value
          field.value = new_value
          field.revised = True

      if update.get("confidence") is not None:
        field.confidence = _clamp_confidence(_normalise_confidence(update["confidence"]))
      elif field.revised:
        field.confidence = 1.0

      identifier = field.id or update.get("name") or ""
      if identifier not in seen_field_ids:
        updated_fields.append(field)
        seen_field_ids.add(identifier)

  updated_tables: List[TableExtraction] = []
  if table_updates:
    tables_by_id = {table.id: table for table in page.tables}
    seen_table_ids: set[str] = set()
    for update in table_updates:
      table_id = update.get("tableId")
      if not table_id:
        raise ValueError("tableId is required for table cell updates")
      table = tables_by_id.get(table_id)
      if not table:
        raise ValueError(f"Table {table_id} not found for update")

      row_index = update.get("row")
      column_index = update.get("column")
      if row_index is None or column_index is None:
        raise ValueError("row and column are required for table cell updates")
      if row_index < 0 or row_index >= len(table.rows):
        raise ValueError(f"Row {row_index} out of bounds for table {table_id}")
      if column_index < 0 or column_index >= len(table.rows[row_index]):
        raise ValueError(f"Column {column_index} out of bounds for table {table_id}")

      cell = table.rows[row_index][column_index]
      new_value = update.get("value", cell.value)
      if new_value != cell.value:
        cell.value = new_value
        cell.confidence = 1.0


      if table_id not in seen_table_ids:
        updated_tables.append(table)
        seen_table_ids.add(table_id)

  job.aggregated = aggregate_fields(job)
  job_store.update(job_id, job)
  save_job_snapshot(job)

  return updated_fields, updated_tables


def delete_job(job_id: str) -> bool:
  """Remove a job's snapshot and any cached in-memory instance."""
  job = job_store.get(job_id)
  if job and job.status.state not in TERMINAL_STATES:
    raise ValueError("Job is still processing")

  removed = False
  if job:
    job_store.remove(job_id)
    removed = True

  job_path = _job_dir(job_id)
  if job_path.exists():
    try:
      shutil.rmtree(job_path)
      removed = True
    except Exception as exc:  # pragma: no cover - best effort cleanup
      logger.exception("Failed to delete job directory %s: %s", job_path, exc)
      raise

  return removed


def get_job_detail(job_id: str) -> Optional[Dict[str, Any]]:
  snapshot_path = _snapshot_path(job_id)
  if not snapshot_path.exists():
    return None
  try:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    summary = data.get("summary") or _job_summary_from_snapshot(data)
    return {
      "jobId": data.get("jobId", job_id),
      "documentName": data.get("documentName", "Unknown"),
      "summary": summary,
      "status": data.get("status", {}),
      "pages": data.get("pages", []),
      "aggregated": data.get("aggregated", {}),
      "metadata": data.get("metadata", {}),
    }
  except Exception as exc:  # pragma: no cover
    logger.exception("Failed to read snapshot for %s: %s", job_id, exc)
    return None


def get_timewindow_metrics() -> Dict[str, Any]:
  summaries = list_job_summaries()
  now = datetime.utcnow().replace(tzinfo=timezone.utc)
  windows = {
    "week": now - timedelta(days=7),
    "month": now - timedelta(days=30),
    "year": now - timedelta(days=365),
  }

  def build_metrics(cutoff: datetime) -> Dict[str, Any]:
    window_jobs = [summary for summary in summaries if summary["finishedAt"] and summary["finishedAt"] >= cutoff]
    return {
      "totalJobs": len(window_jobs),
      "totalPages": sum(job["totalPages"] for job in window_jobs),
      "totalFields": sum(job["totalFields"] for job in window_jobs),
      "totalTables": sum(job["totalTables"] for job in window_jobs),
      "totalProcessingMs": sum(job.get("totalProcessingMs") or 0 for job in window_jobs),
    }

  return {name: build_metrics(cutoff) for name, cutoff in windows.items()}


def _job_summary(job: ExtractionJob) -> Dict[str, Any]:
  total_fields = sum(len(page.fields) for page in job.pages)
  total_tables = sum(len(page.tables) for page in job.pages)
  finished_at = job.status.finished_at
  started_at = job.status.started_at
  processing_ms = None
  if finished_at and started_at:
    processing_ms = int((finished_at - started_at).total_seconds() * 1000)
  confidence_buckets, low_conf_count = _compute_confidence_stats_for_job(job)

  return {
    "totalPages": len(job.pages),
    "totalFields": total_fields,
    "totalTables": total_tables,
    "totalProcessingMs": processing_ms,
    "startedAt": started_at.isoformat() if started_at else None,
    "finishedAt": finished_at.isoformat() if finished_at else None,
    "confidenceBuckets": confidence_buckets,
    "lowConfidenceCount": low_conf_count,
  }


def _job_summary_from_snapshot(data: Dict[str, Any]) -> Dict[str, Any]:
  summary = data.get("summary")
  if summary:
    pages = data.get("pages", [])
    confidence_buckets = summary.get("confidenceBuckets")
    low_conf_count = summary.get("lowConfidenceCount")
    if confidence_buckets is None or len(confidence_buckets) != CONFIDENCE_BUCKET_COUNT or low_conf_count is None:
      buckets, low_count = _compute_confidence_stats_from_page_dicts(pages)
      summary = {
        **summary,
        "confidenceBuckets": buckets,
        "lowConfidenceCount": low_count,
      }
    else:
      summary.setdefault("lowConfidenceCount", 0)
    return summary
  pages = data.get("pages", [])
  total_fields = sum(len(page.get("fields", [])) for page in pages)
  total_tables = sum(len(page.get("tables", [])) for page in pages)
  status = data.get("status", {})
  started_at = status.get("startedAt")
  finished_at = status.get("finishedAt")
  processing_ms = None
  if started_at and finished_at:
    start = _parse_datetime(started_at)
    finish = _parse_datetime(finished_at)
    if start and finish:
      processing_ms = int((finish - start).total_seconds() * 1000)
  confidence_buckets, low_conf_count = _compute_confidence_stats_from_page_dicts(pages)
  return {
    "totalPages": len(pages),
    "totalFields": total_fields,
    "totalTables": total_tables,
    "totalProcessingMs": processing_ms,
    "startedAt": started_at,
    "finishedAt": finished_at,
    "confidenceBuckets": confidence_buckets,
    "lowConfidenceCount": low_conf_count,
  }


def _status_to_dict(status: JobStatus) -> Dict[str, Any]:
  return {
    "jobId": status.job_id,
    "totalPages": status.total_pages,
    "processedPages": status.processed_pages,
    "state": status.state,
    "errors": status.errors,
    "startedAt": status.started_at.isoformat() if status.started_at else None,
    "finishedAt": status.finished_at.isoformat() if status.finished_at else None,
  }


def _page_to_dict(page: PageExtraction, job_dir: Path) -> Dict[str, Any]:
  image_path = None
  if page.image_path:
    try:
      image_path = str(page.image_path.relative_to(job_dir))
    except ValueError:
      image_path = str(page.image_path)
  return {
    "pageNumber": page.page_number,
    "status": page.status,
    "fields": [asdict(field) for field in page.fields],
    "tables": [asdict(table) for table in page.tables],
    "imagePath": image_path,
    "imageMime": page.image_mime,
    "markdownText": page.markdown_text,
    "errorMessage": page.error_message,
    "rotationApplied": getattr(page, "rotation_applied", 0),
    "documentTypeHint": getattr(page, "document_type_hint", None),
    "documentTypeConfidence": getattr(page, "document_type_confidence", None),
  }


def _page_from_dict(data: Dict[str, Any], job_dir: Path) -> PageExtraction:
  page_number = data.get("pageNumber", data.get("page_number", 1))
  fields_payload = data.get("fields") or []
  fields = [_field_from_dict(field_data, default_page=page_number) for field_data in fields_payload]
  tables_payload = data.get("tables") or data.get("table_extractions") or []
  tables = [_table_from_dict(table_data, default_page=page_number) for table_data in tables_payload]
  image_path = data.get("imagePath") or data.get("image_path")
  path_obj = None
  if image_path:
    try:
      path_obj = job_dir / image_path
    except Exception:  # pragma: no cover - defensive
      path_obj = Path(image_path)
  return PageExtraction(
    page_number=page_number,
    status=data.get("status") or data.get("page_status", "completed"),
    image_path=path_obj,
    image_mime=data.get("imageMime") or data.get("image_mime"),
    markdown_text=data.get("markdownText") or data.get("markdown_text"),
    fields=fields,
    tables=tables,
    error_message=data.get("errorMessage") or data.get("error_message"),
    rotation_applied=data.get("rotationApplied", data.get("rotation_applied", 0)),
    document_type_hint=data.get("documentTypeHint") or data.get("document_type_hint"),
    document_type_confidence=data.get("documentTypeConfidence") or data.get("document_type_confidence"),
  )


def _field_from_dict(data: Dict[str, Any], *, default_page: int = 0) -> FieldExtraction:
  bbox_data = data.get("bbox") or data.get("bounding_box")
  bbox = None
  if isinstance(bbox_data, dict):
    bbox = BoundingBox(
      x=float(bbox_data.get("x", 0.0)),
      y=float(bbox_data.get("y", 0.0)),
      width=float(bbox_data.get("width", 0.0)),
      height=float(bbox_data.get("height", 0.0)),
    )
  name = data.get("name") or data.get("field_name") or data.get("label") or ""
  value = data.get("value", "")
  if value is None:
    value = ""
  return FieldExtraction(
    id=data.get("id") or data.get("field_id") or name,
    page=data.get("page") or data.get("page_number") or default_page,
    name=name,
    value=str(value),
    confidence=_normalise_confidence(data.get("confidence", 0.0)),
    bbox=bbox,
    source_type=data.get("source_type") or data.get("sourceType") or data.get("source"),
    revised=data.get("revised", data.get("was_edited", False)),
    original_value=data.get("original_value") or data.get("normalized_value"),
  )


def _table_from_dict(data: Dict[str, Any], *, default_page: int = 0) -> TableExtraction:
  columns = [_column_from_dict(col) for col in data.get("columns", data.get("table_columns", []))]
  rows: List[List[TableCell]] = []
  for row in data.get("rows", data.get("table_rows", [])):
    if isinstance(row, list):
      rows.append([_cell_from_dict(cell) for cell in row])
    elif isinstance(row, dict):
      rows.append([_cell_from_dict(cell) for cell in row.values()])

  row_start_index = data.get("rowStartIndex", data.get("row_start_index", 0))

  if not rows:
    raw_cells = data.get("cells") or data.get("table_cells")
    if isinstance(raw_cells, list) and raw_cells:
      cell_map: Dict[tuple[int, int], Dict[str, Any]] = {}
      header_rows: set[int] = set()
      max_column = -1

      for raw_cell in raw_cells:
        if not isinstance(raw_cell, dict):
          continue
        row_index = int(raw_cell.get("row", 0))
        column_index = int(raw_cell.get("column", 0))
        adapted = dict(raw_cell)
        if "value" not in adapted:
          adapted["value"] = adapted.get("content", "")
        if "bbox" not in adapted and isinstance(adapted.get("bounding_box"), dict):
          adapted["bbox"] = adapted["bounding_box"]
        cell_map[(row_index, column_index)] = adapted
        if adapted.get("is_header"):
          header_rows.add(row_index)
        if column_index > max_column:
          max_column = column_index

      if cell_map:
        column_count = max(len(columns), max_column + 1)
        header_row_index = min(header_rows) if header_rows else None

        new_columns: List[TableColumn] = []
        for column_index in range(column_count):
          existing = columns[column_index] if column_index < len(columns) else None
          key = existing.key if existing else f"col_{column_index}"
          header_text = existing.header if existing else f"Column {column_index + 1}"
          column_type = existing.type if existing else None
          confidence_value = existing.confidence if existing else None

          if header_row_index is not None:
            header_cell = cell_map.get((header_row_index, column_index))
            if header_cell:
              header_value = str(header_cell.get("value") or header_cell.get("content") or "").strip()
              if header_value:
                header_text = header_value
              if header_cell.get("confidence") is not None:
                confidence_value = _normalise_confidence(header_cell.get("confidence"))

          new_columns.append(
            TableColumn(
              key=key,
              header=header_text,
              type=column_type,
              confidence=confidence_value,
            )
          )

        columns = new_columns

        data_row_indices = sorted({row for (row, _) in cell_map.keys() if row not in header_rows})
        if not data_row_indices:
          data_row_indices = sorted({row for (row, _) in cell_map.keys()})

        if row_start_index == 0 and data_row_indices:
          row_start_index = min(data_row_indices)

        for row_index in data_row_indices:
          row_cells: List[TableCell] = []
          for column_index in range(len(columns)):
            raw_cell = cell_map.get((row_index, column_index))
            if raw_cell:
              row_cells.append(_cell_from_dict(raw_cell))
            else:
              row_cells.append(TableCell(value=""))
          rows.append(row_cells)

  bbox_data = data.get("bbox") or data.get("bounding_box")
  bbox = None
  if isinstance(bbox_data, dict):
    bbox = BoundingBox(
      x=float(bbox_data.get("x", 0.0)),
      y=float(bbox_data.get("y", 0.0)),
      width=float(bbox_data.get("width", 0.0)),
      height=float(bbox_data.get("height", 0.0)),
    )
  return TableExtraction(
    id=data.get("id") or data.get("table_id"),
    page=data.get("page", data.get("page_number", default_page)),
    caption=data.get("caption"),
    confidence=_normalise_confidence(data.get("confidence", 0.0)) if data.get("confidence") is not None else None,
    columns=columns,
    rows=rows,
    bbox=bbox,
    normalized=data.get("normalized", True),
    table_group_id=data.get("tableGroupId") or data.get("table_group_id"),
    continuation_of=data.get("continuationOf") or data.get("continuation_of"),
    inferred_headers=data.get("inferredHeaders", data.get("inferred_headers", False)),
    row_start_index=row_start_index,
  )


def _column_from_dict(data: Dict[str, Any]) -> TableColumn:
  return TableColumn(
    key=data.get("key") or data.get("column_key", ""),
    header=data.get("header") or data.get("name", ""),
    type=data.get("type"),
    confidence=data.get("confidence"),
  )


def _cell_from_dict(data: Dict[str, Any]) -> TableCell:
  bbox_data = data.get("bbox") or data.get("bounding_box")
  bbox = None
  if isinstance(bbox_data, dict):
    bbox = BoundingBox(
      x=float(bbox_data.get("x", 0.0)),
      y=float(bbox_data.get("y", 0.0)),
      width=float(bbox_data.get("width", 0.0)),
      height=float(bbox_data.get("height", 0.0)),
    )
  return TableCell(
    value=str(data.get("value", data.get("text", ""))),
    confidence=data.get("confidence"),
    bbox=bbox,
  )


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
  if not value:
    return None
  try:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
      return dt.replace(tzinfo=timezone.utc)
    return dt
  except ValueError:
    return None


def _ensure_timezone(value: Optional[datetime]) -> Optional[datetime]:
  if not value:
    return None
  if value.tzinfo is None:
    return value.replace(tzinfo=timezone.utc)
  return value
