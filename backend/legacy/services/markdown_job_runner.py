from __future__ import annotations

import logging
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import List

from backend.models.job import ExtractionJob, JobStatus, PageExtraction

from . import table_grouping
from .aggregation import aggregate_fields
from .history_service import save_job_snapshot
from .markdown_llm import (
    PageExtractionPayload,
    extract_page_payload,
    split_markdown_pages,
)
from .mapping_service import generate_canonical_bundle
from .store import job_store
from .vision_service import parse_fields, parse_tables

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)
BASE_OUTPUT_DIR = Path("backend_data")
BASE_OUTPUT_DIR.mkdir(exist_ok=True)


def create_markdown_job(markdown_path: Path, original_filename: str) -> ExtractionJob:
    job_id = uuid.uuid4().hex
    output_dir = BASE_OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    stored_markdown = output_dir / "source.md"
    shutil.copy2(markdown_path, stored_markdown)

    try:
        markdown_text = stored_markdown.read_text(encoding="utf-8")
    except Exception:  # pragma: no cover - defensive
        markdown_text = ""

    page_texts = split_markdown_pages(markdown_text)
    if not page_texts:
        page_texts = [markdown_text]

    pages: List[PageExtraction] = [
        PageExtraction(page_number=index + 1, status="pending")
        for index in range(len(page_texts))
    ]

    for index, page in enumerate(pages):
        page.markdown_text = page_texts[index]

    status = JobStatus(job_id=job_id, total_pages=len(pages), state="queued")
    job = ExtractionJob(
        status=status,
        pdf_path=stored_markdown,
        output_dir=output_dir,
        pages=pages,
    )
    job.metadata["originalFilename"] = original_filename
    job.metadata["sourceFormat"] = "markdown"
    job.metadata["pageSplits"] = len(page_texts)
    job.metadata.setdefault("pageClassifications", [])
    job.metadata.setdefault("documentCategories", [])
    job.metadata.setdefault("documentTypes", [])
    job.metadata.setdefault("pageCategories", {})
    job.aggregated = {"fields": []}

    job_store.add(job)
    save_job_snapshot(job)
    return job


def start_processing(job: ExtractionJob) -> None:
    job_store.update(job.status.job_id, job)
    _executor.submit(_process_markdown_job, job.status.job_id)


def _process_markdown_job(job_id: str) -> None:
    job = job_store.get(job_id)
    if not job:
        logger.error("Markdown job %s not found", job_id)
        return

    job.status.state = "running"
    job.status.started_at = datetime.utcnow()
    job_store.update(job_id, job)
    save_job_snapshot(job)

    markdown_path = Path(job.pdf_path)
    try:
        markdown_text = markdown_path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive I/O
        logger.exception("Failed to read markdown source for job %s: %s", job_id, exc)
        job.status.errors.append({"stage": "ingest", "message": str(exc)})
        job.status.state = "error"
        job.status.finished_at = datetime.utcnow()
        job_store.update(job_id, job)
        save_job_snapshot(job)
        return

    page_texts = split_markdown_pages(markdown_text)
    if not page_texts:
        page_texts = [markdown_text]

    if len(job.pages) < len(page_texts):
        for index in range(len(job.pages), len(page_texts)):
            job.pages.append(PageExtraction(page_number=index + 1, status="pending"))
    elif len(job.pages) > len(page_texts):
        job.pages = job.pages[: len(page_texts)]
    job.status.total_pages = len(page_texts)

    page_classifications: List[dict] = []

    for index, page in enumerate(job.pages):
        page_text = page_texts[index] if index < len(page_texts) else ""
        page.markdown_text = page_text
        page.status = "processing"
        page.error_message = None
        try:
            extraction_payload: PageExtractionPayload = extract_page_payload(
                page_text,
                page.page_number,
                debug_dir=job.output_dir,
            )
            payload = extraction_payload.payload
            page.fields = parse_fields(page.page_number, payload)
            page.tables = parse_tables(page.page_number, payload)

            doc_type = payload.get("documentType") or {}
            page.document_type_hint = doc_type.get("label")
            page.document_type_confidence = doc_type.get("confidence")
            if page.document_type_hint:
                page_classifications.append(
                    {
                        "page": page.page_number,
                        "label": page.document_type_hint,
                        "confidence": page.document_type_confidence,
                        "reasons": doc_type.get("reasons", []),
                    }
                )
            page.status = "completed"
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Markdown extraction failed for job %s page %s: %s", job_id, page.page_number, exc)
            page.status = "error"
            page.error_message = str(exc)
            job.status.errors.append({"page": page.page_number, "message": str(exc)})

        job.status.processed_pages = sum(
            1 for p in job.pages if p.status in {"completed", "error"}
        )
        job_store.update(job_id, job)
        save_job_snapshot(job)

    if page_classifications:
        job.metadata["pageClassifications"] = page_classifications
        job.metadata["pageCategories"] = {
            entry["page"]: entry.get("label")
            for entry in page_classifications
            if entry.get("page") and entry.get("label")
        }
        ordered = []
        for entry in page_classifications:
            label = entry.get("label")
            if label and label not in ordered:
                ordered.append(label)
        job.metadata["documentCategories"] = ordered
        if ordered and not job.document_type:
            job.document_type = ordered[0]

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
        if job.canonical:
            job.metadata["canonicalDocumentTypes"] = job.canonical.get("documentTypes")
            job.metadata["documentCategories"] = job.canonical.get("documentCategories", [])
            job.metadata["documentTypes"] = job.canonical.get("documentTypes", [])
        if not job.document_type:
            document_types = (job.canonical or {}).get("documentTypes")
            if document_types:
                job.document_type = document_types[0]
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Canonical generation failed for markdown job %s: %s", job_id, exc)
        job.status.errors.append({"stage": "mapping", "message": str(exc)})

    job.status.state = "completed" if not job.status.errors else "partial"
    job.status.finished_at = datetime.utcnow()
    job_store.update(job_id, job)
    save_job_snapshot(job)
