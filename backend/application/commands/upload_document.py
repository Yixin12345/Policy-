"""Command handler for creating jobs from uploaded documents."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend.models.job import ExtractionJob

JobCreator = Callable[[Path, str], ExtractionJob]


@dataclass(frozen=True)
class UploadDocumentCommand:
    """Command describing an uploaded document ready to be persisted."""

    file_path: Path
    filename: str
    media_type: str = "pdf"


class UploadDocumentHandler:
    """Handles creation of jobs for uploaded documents."""

    def __init__(self, pdf_job_creator: JobCreator, markdown_job_creator: JobCreator):
        self._create_pdf_job = pdf_job_creator
        self._create_markdown_job = markdown_job_creator

    def handle(self, command: UploadDocumentCommand) -> ExtractionJob:
        if not command.file_path.exists():
            raise FileNotFoundError(f"Uploaded file not found at {command.file_path}")

        media_type = (command.media_type or "pdf").lower()
        if media_type in {"md", "markdown", "mmd"}:
            return self._create_markdown_job(command.file_path, command.filename)

        return self._create_pdf_job(command.file_path, command.filename)
