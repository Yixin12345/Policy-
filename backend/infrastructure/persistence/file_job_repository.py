"""File-based implementation of JobRepository working with domain aggregates."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.repositories.job_repository import JobRepository
from backend.domain.value_objects.job_status import JobState, JobStatus
from backend.domain.exceptions import RepositoryError

logger = logging.getLogger(__name__)


class FileJobRepository(JobRepository):
    """Persist jobs as JSON snapshots on disk."""

    def __init__(self, base_dir: str = "backend_data") -> None:
        self.base_dir = Path(base_dir)
        self.snapshot_filename = "job_snapshot.json"
        self._ensure_base_dir()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def save(self, job: Job) -> None:
        snapshot = self._job_to_snapshot(job)
        job_dir = self._job_dir(job.job_id)
        try:
            job_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - disk failure
            raise RepositoryError(f"Failed to create directory for job {job.job_id}", exc)

        snapshot_path = self._snapshot_path(job.job_id)
        tmp_path = snapshot_path.with_suffix(".tmp")

        try:
            tmp_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            tmp_path.replace(snapshot_path)
            logger.debug("Saved job %s", job.job_id)
        except (OSError, TypeError, ValueError) as exc:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise RepositoryError(f"Failed to save job {job.job_id}", exc)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def find_by_id(self, job_id: str) -> Optional[Job]:
        data = self._load_snapshot(job_id)
        if data is None:
            return None
        try:
            return self._snapshot_to_job(data)
        except Exception as exc:  # pragma: no cover - unexpected snapshot structure
            raise RepositoryError(f"Failed to hydrate job {job_id}", exc)

    def find_all(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> List[Job]:
        jobs: List[Job] = []
        for job_dir in self.base_dir.iterdir():
            if not job_dir.is_dir():
                continue
            data = self._load_snapshot(job_dir.name)
            if data is None:
                continue
            try:
                jobs.append(self._snapshot_to_job(data))
            except Exception as exc:
                logger.warning("Skipping job %s due to snapshot error: %s", job_dir.name, exc)
                continue

        jobs.sort(key=lambda job: job.created_at, reverse=sort_desc)

        start = offset
        end = None if limit is None else offset + limit
        return jobs[start:end]

    def find_by_status(
        self,
        status: str,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> List[Job]:
        status_lower = status.lower()
        filtered = [job for job in self.find_all() if job.status.state.value == status_lower]
        filtered.sort(key=lambda job: job.created_at, reverse=sort_desc)
        start = offset
        end = None if limit is None else offset + limit
        return filtered[start:end]

    def delete(self, job_id: str) -> bool:
        job_dir = self._job_dir(job_id)
        if not job_dir.exists():
            return False
        try:
            import shutil

            shutil.rmtree(job_dir)
            logger.info("Deleted job %s", job_id)
            return True
        except OSError as exc:  # pragma: no cover - disk failure
            raise RepositoryError(f"Failed to delete job {job_id}", exc)

    def exists(self, job_id: str) -> bool:
        return self._snapshot_path(job_id).exists()

    def count(self, status: Optional[str] = None) -> int:
        if status is None:
            return sum(1 for job_dir in self.base_dir.iterdir() if self._snapshot_path(job_dir.name).exists())
        status_lower = status.lower()
        return sum(
            1
            for job in self.find_all()
            if job.status.state.value == status_lower
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_base_dir(self) -> None:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - disk failure
            raise RepositoryError(f"Failed to create base directory {self.base_dir}", exc)

    def _job_dir(self, job_id: str) -> Path:
        return self.base_dir / job_id

    def _snapshot_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / self.snapshot_filename

    def _load_snapshot(self, job_id: str) -> Optional[dict]:
        snapshot_path = self._snapshot_path(job_id)
        if not snapshot_path.exists():
            return None
        try:
            return json.loads(snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RepositoryError(f"Corrupted snapshot for job {job_id}", exc)
        except OSError as exc:  # pragma: no cover - disk failure
            raise RepositoryError(f"Failed to read snapshot for job {job_id}", exc)

    # Snapshot -> Domain ------------------------------------------------
    def _snapshot_to_job(self, data: dict) -> Job:
        job_id = data.get("job_id") or data.get("jobId")
        if not job_id:
            raise RepositoryError("Snapshot missing job_id")

        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

        filename = (
            data.get("filename")
            or data.get("documentName")
            or metadata.get("filename")
            or ""
        )
        status_entry = data.get("status")
        status_total_pages = None
        if isinstance(status_entry, dict):
            status_total_pages = status_entry.get("totalPages") or status_entry.get("total_pages")

        total_pages = (
            data.get("total_pages")
            or data.get("page_count")
            or data.get("totalPages")
            or status_total_pages
        )

        created_at = self._parse_datetime(
            data.get("created_at")
            or data.get("createdAt")
            or data.get("status", {}).get("startedAt")
        )
        updated_at = self._parse_datetime(
            data.get("updated_at")
            or data.get("updatedAt")
            or data.get("status", {}).get("finishedAt")
            or data.get("status", {}).get("updatedAt")
        ) or created_at

        status = self._extract_status(data)

        pages: List[PageExtraction] = []
        for page_entry in data.get("pages", []):
            if isinstance(page_entry, dict):
                pages.append(self._snapshot_to_page(job_id, page_entry))
            elif isinstance(page_entry, (int, float)):
                try:
                    pages.append(PageExtraction.create(page_number=int(page_entry)))
                except ValueError:
                    logger.debug("Skipping invalid page entry %s for job %s", page_entry, job_id)
            else:
                logger.debug("Skipping unsupported page entry type %s", type(page_entry))

        source_path = data.get("source_path") or data.get("sourcePdf")

        return Job(
            job_id=job_id,
            filename=filename,
            status=status,
            total_pages=total_pages,
            pages=pages,
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
            source_path=source_path,
        )

    def _snapshot_to_page(self, job_id: str, data: dict) -> PageExtraction:
        if isinstance(data, PageExtraction):
            return data

        normalized = {
            "page_number": data.get("page_number") or data.get("pageNumber") or data.get("page") or 1,
            "fields": [self._normalize_field_dict(field) for field in data.get("fields", [])],
            "tables": [self._normalize_table_dict(table) for table in data.get("tables", [])],
            "image_path": self._resolve_image_path(job_id, data.get("image_path") or data.get("imagePath")),
            "has_edits": data.get("has_edits", data.get("hasEdits", False)),
            "status": data.get("status") or data.get("page_status", "completed"),
            "markdown_text": data.get("markdownText") or data.get("markdown_text"),
            "image_mime": data.get("imageMime") or data.get("image_mime"),
            "rotation_applied": data.get("rotationApplied", data.get("rotation_applied", 0)),
            "document_type_hint": data.get("documentTypeHint") or data.get("document_type_hint"),
            "document_type_confidence": data.get("documentTypeConfidence") or data.get("document_type_confidence"),
            "error_message": data.get("errorMessage") or data.get("error_message"),
        }

        page = PageExtraction.from_dict(normalized)
        return page.mark_reviewed() if normalized["has_edits"] else page

    def _resolve_image_path(self, job_id: str, image_path: Optional[str]) -> Optional[str]:
        if not image_path:
            return None
        path = Path(image_path)
        if path.is_absolute():
            return str(path)
        candidate = self._job_dir(job_id) / path
        if candidate.exists():
            return str(candidate)
        return str(path)

    def _normalize_field_dict(self, data: dict) -> dict:
        if isinstance(data, dict):
            return {
                "id": data.get("id") or data.get("field_id") or data.get("uuid"),
                "field_name": data.get("field_name") or data.get("name") or "",
                "field_type": data.get("field_type") or data.get("type") or "text",
                "value": data.get("value") or data.get("text") or "",
                "normalized_value": data.get("normalized_value") or data.get("normalizedValue"),
                "confidence": self._extract_confidence_value(data.get("confidence") or data.get("score")),
                "bounding_box": self._normalize_bbox(data.get("bounding_box") or data.get("bbox")),
                "page_number": data.get("page_number") or data.get("page") or 1,
                "extracted_at": data.get("extracted_at") or data.get("extractedAt"),
                "source": data.get("source") or data.get("source_type") or "unknown",
                "was_edited": data.get("was_edited") or data.get("revised") or False,
            }
        return {
            "field_name": "",
            "field_type": "text",
            "value": str(data),
            "confidence": 0.0,
            "page_number": 1,
        }

    def _normalize_table_dict(self, data: dict) -> dict:
        if not isinstance(data, dict):
            return {
                "id": None,
                "title": None,
                "page_number": 1,
                "confidence": 0.0,
                "bounding_box": None,
                "cells": [],
                "created_at": None,
                "updated_at": None,
            }

        confidence = self._extract_confidence_value(data.get("confidence") or data.get("score"))
        normalized_cells: list[dict] = []
        column_headers: list[tuple[int, str]] = []
        column_keys: list[str] = []

        raw_columns = data.get("columns")
        if isinstance(raw_columns, list):
            for index, column in enumerate(raw_columns):
                label = None
                key = None
                if not isinstance(column, dict):
                    label = str(column)
                    key = label
                else:
                    label = (
                        column.get("header")
                        or column.get("name")
                        or column.get("title")
                        or column.get("key")
                    )
                    key = (
                        column.get("key")
                        or column.get("name")
                        or column.get("title")
                        or column.get("header")
                    )
                if label:
                    column_headers.append((index, str(label)))
                column_keys.append(str(key) if key else f"column_{index}")
        else:
            column_keys = []

        header_row_offset = 1 if column_headers else 0

        if isinstance(data.get("cells"), list):
            for cell in data["cells"]:
                if not isinstance(cell, dict):
                    continue
                raw_confidence = cell.get("confidence")
                confidence_value = (
                    self._extract_confidence_value(raw_confidence)
                    if raw_confidence is not None
                    else None
                )
                cell_entry = {
                    "row": cell.get("row", 0),
                    "column": cell.get("column", 0),
                    "content": cell.get("content") or cell.get("value") or "",
                    "rowspan": cell.get("rowspan", 1),
                    "colspan": cell.get("colspan", 1),
                    "is_header": cell.get("is_header") or cell.get("isHeader") or False,
                    "bounding_box": self._normalize_bbox(cell.get("bounding_box")),
                }
                if confidence_value is not None:
                    cell_entry["confidence"] = confidence_value
                normalized_cells.append(cell_entry)

        elif isinstance(data.get("rows"), list):
            for column_index, label in column_headers:
                normalized_cells.append(
                    self._create_table_cell_entry(
                        0,
                        column_index,
                        {"content": label, "is_header": True},
                    )
                )

            for row_index, row in enumerate(data["rows"]):
                if isinstance(row, dict):
                    keys = column_keys or list(row.keys())
                    for col_index, key in enumerate(keys):
                        cell_payload = row.get(key)
                        if cell_payload is None and isinstance(key, str):
                            cell_payload = row.get(key.lower())
                        normalized_cells.append(
                            self._create_table_cell_entry(
                                header_row_offset + row_index,
                                col_index,
                                cell_payload,
                            )
                        )
                elif isinstance(row, list):
                    for col_index, value in enumerate(row):
                        normalized_cells.append(
                            self._create_table_cell_entry(
                                header_row_offset + row_index,
                                col_index,
                                value,
                            )
                        )
                else:
                    normalized_cells.append(
                        self._create_table_cell_entry(
                            header_row_offset + row_index,
                            0,
                            row,
                        )
                    )

        return {
            "id": data.get("id"),
            "title": data.get("title") or data.get("table_name"),
            "page_number": data.get("page_number") or data.get("page") or 1,
            "confidence": confidence,
            "bounding_box": self._normalize_bbox(data.get("bounding_box")),
            "cells": normalized_cells,
            "created_at": data.get("created_at") or data.get("createdAt"),
            "updated_at": data.get("updated_at") or data.get("updatedAt"),
        }

    def _create_table_cell_entry(self, row: int, column: int, payload: Any) -> dict:
        cell_value = payload
        cell_confidence = None
        bbox = None
        is_header = False
        rowspan = 1
        colspan = 1

        if isinstance(payload, dict):
            cell_value = (
                payload.get("value")
                or payload.get("text")
                or payload.get("content")
                or ""
            )
            if payload.get("confidence") is not None:
                cell_confidence = self._extract_confidence_value(payload.get("confidence"))
            bbox = self._normalize_bbox(payload.get("bbox") or payload.get("bounding_box"))
            is_header = payload.get("is_header") or payload.get("isHeader") or False
            rowspan = payload.get("rowspan", rowspan)
            colspan = payload.get("colspan", colspan)
        elif payload is None:
            cell_value = ""

        entry = {
            "row": row,
            "column": column,
            "content": cell_value if isinstance(cell_value, str) else str(cell_value),
            "rowspan": rowspan,
            "colspan": colspan,
            "is_header": is_header,
            "bounding_box": bbox,
        }
        if cell_confidence is not None:
            entry["confidence"] = cell_confidence
        return entry

    @staticmethod
    def _extract_confidence_value(value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, dict):
            maybe_value = value.get("value")
            if maybe_value is not None:
                try:
                    return float(maybe_value)
                except (TypeError, ValueError):
                    return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _normalize_bbox(value):
        if isinstance(value, dict):
            return value
        return None

    def _extract_status(self, data: dict) -> JobStatus:
        status_entry = data.get("status")
        error_message: Optional[str] = None
        progress = 0.0
        state_value = "queued"

        if isinstance(status_entry, dict):
            state_value = status_entry.get("state") or status_entry.get("status") or "queued"
            processed = status_entry.get("processedPages") or status_entry.get("processed_pages")
            total = status_entry.get("totalPages") or status_entry.get("total_pages")
            if processed is not None and total:
                try:
                    progress = float(processed) / max(float(total), 1.0)
                except (TypeError, ValueError):
                    progress = 0.0
            else:
                progress = float(status_entry.get("progress", 0.0))
                if progress > 1:
                    progress = progress / 100.0
            errors = status_entry.get("errors")
            if isinstance(errors, list) and errors:
                error_message = "; ".join(str(err) for err in errors)
            elif isinstance(errors, str):
                error_message = errors
        else:
            state_value = str(status_entry or data.get("state") or data.get("job_status") or "queued")
            progress = float(data.get("progress", 0.0))
            if progress > 1:
                progress = progress / 100.0
            error_message = data.get("error_message")

        try:
            job_state = JobState(state_value.lower())
        except ValueError:
            job_state = JobState.ERROR
            if not error_message:
                error_message = f"Unknown state '{state_value}'"

        return JobStatus(
            state=job_state,
            progress=progress,
            error_message=error_message,
        )

    def _job_to_snapshot(self, job: Job) -> dict:
        return {
            "job_id": job.job_id,
            "filename": job.filename,
            "status": job.status.state.value,
            "progress": job.status.progress,
            "error_message": job.status.error_message,
            "total_pages": job.total_pages,
            "processed_pages": len(job.pages),
            "pages": [page.to_dict() for page in job.pages],
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "source_path": job.source_path,
        }

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            return None
