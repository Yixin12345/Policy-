from __future__ import annotations

import logging
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from ...models.job import ExtractionJob, JobStatus
from .aggregation import aggregate_fields
from .mapping_service import generate_canonical_bundle
from .history_service import load_job_from_snapshot, save_job_snapshot
from .pdf_service import pdf_to_images
from .store import job_store
from . import table_grouping
from .vision_service import call_vision_model, parse_fields, parse_tables

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)
BASE_OUTPUT_DIR = Path("backend_data")
BASE_OUTPUT_DIR.mkdir(exist_ok=True)


def create_job(pdf_path: Path, original_filename: str) -> ExtractionJob:
  job_id = uuid.uuid4().hex
  output_dir = BASE_OUTPUT_DIR / job_id
  output_dir.mkdir(parents=True, exist_ok=True)
  stored_pdf_path = output_dir / "source.pdf"
  shutil.copy2(pdf_path, stored_pdf_path)
  pages = pdf_to_images(stored_pdf_path, output_dir)

  status = JobStatus(job_id=job_id, total_pages=len(pages), state="queued")
  job = ExtractionJob(status=status, pdf_path=stored_pdf_path, output_dir=output_dir, pages=pages)
  job.metadata["originalFilename"] = original_filename
  job_store.add(job)
  save_job_snapshot(job)
  return job


def start_processing(job: ExtractionJob) -> None:
  _executor.submit(_process_job, job.status.job_id)


def _process_job(job_id: str) -> None:
  job = job_store.get(job_id)
  if not job:
    logger.error("Job %s not found", job_id)
    return

  job.status.state = "running"
  job.status.started_at = datetime.utcnow()
  job_store.update(job_id, job)
  save_job_snapshot(job)

  page_classifications = []

  for page in job.pages:
    if not page.image_path:
      continue
    try:
      page.status = "processing"
      payload = call_vision_model(str(page.image_path), page.page_number)
      page.fields = parse_fields(page.page_number, payload)
      page.tables = parse_tables(page.page_number, payload)
      doc_type_info = payload.get("documentType") or {}
      page.document_type_hint = doc_type_info.get("label")
      page.document_type_confidence = doc_type_info.get("confidence")
      if page.document_type_hint:
        page_classifications.append(
          {
            "page": page.page_number,
            "label": page.document_type_hint,
            "confidence": page.document_type_confidence,
            "reasons": doc_type_info.get("reasons", []),
          }
        )
      page.status = "completed"
    except Exception as exc:  # pylint: disable=broad-except
      page.status = "error"
      page.error_message = str(exc)
      job.status.errors.append({"page": page.page_number, "message": str(exc)})
      logger.exception("Failed to process page %s: %s", page.page_number, exc)

    job.status.processed_pages = sum(1 for p in job.pages if p.status in {"completed", "error"})
    job_store.update(job_id, job)
    save_job_snapshot(job)

  if page_classifications:
    job.metadata["pageClassifications"] = page_classifications
    job.metadata["pageCategories"] = {
      entry["page"]: entry["label"]
      for entry in page_classifications
      if entry.get("label")
    }
    ordered_categories: list[str] = []
    for entry in page_classifications:
      label = entry.get("label")
      if not label or label in ordered_categories:
        continue
      ordered_categories.append(label)
    job.metadata["documentCategories"] = ordered_categories
    best_label = max(
      page_classifications,
      key=lambda item: (item.get("confidence") or 0.0, item.get("page", 0)),
    ).get("label")
    job.document_type = best_label
  else:
    job.metadata.pop("pageClassifications", None)
    job.metadata.pop("pageCategories", None)
    job.metadata.pop("documentCategories", None)

  job.aggregated = aggregate_fields(job)
  table_groups = table_grouping.assign_table_groups(job.pages)
  merged_tables = table_grouping.merge_table_segments(table_groups)
  job.metadata["tableGroups"] = {
    group_id: {
      "pages": [segment.page for segment in segments],
      "rowCount": sum(len(segment.rows) for segment in segments),
      "columns": [column.header for column in (segments[0].columns if segments else [])],
    }
    for group_id, segments in table_groups.items()
  }
  job.metadata["mergedTables"] = {
    group_id: {
      "id": table.id,
      "rows": [[cell.value for cell in row] for row in table.rows],
      "columns": [column.header for column in table.columns],
    }
    for group_id, table in merged_tables.items()
  }

  try:
    canonical_bundle, trace = generate_canonical_bundle(job)
    job.canonical = canonical_bundle
    job.mapping_trace = trace
    if not job.document_type:
      document_types = canonical_bundle.get("documentTypes") or []
      if document_types:
        job.document_type = document_types[0]
    job.metadata["canonicalDocumentTypes"] = job.canonical.get("documentTypes") if job.canonical else None
  except Exception as exc:  # pragma: no cover - defensive mapping failure
    logger.exception("Failed to generate canonical bundle for job %s: %s", job_id, exc)
    job.status.errors.append({"stage": "mapping", "message": str(exc)})

  job.status.state = "completed" if not job.status.errors else "partial"
  job.status.finished_at = datetime.utcnow()
  job_store.update(job_id, job)
  save_job_snapshot(job)


def get_job(job_id: str) -> Optional[ExtractionJob]:
  job = job_store.get(job_id)
  if job:
    return job
  snapshot_job = load_job_from_snapshot(job_id)
  if snapshot_job:
    job_store.add(snapshot_job)
    return snapshot_job
  return None
