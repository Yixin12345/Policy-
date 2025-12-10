from __future__ import annotations

from backend.models.job import ExtractionJob
from .job_runner import start_processing as start_pdf_processing
from .markdown_job_runner import start_processing as start_markdown_processing


def start_job_processing(job: ExtractionJob) -> None:
    """Dispatch job processing based on source format."""
    source_format = (job.metadata or {}).get("sourceFormat", "pdf").lower()
    if source_format in {"markdown", "md", "mmd"}:
        start_markdown_processing(job)
        return

    start_pdf_processing(job)
