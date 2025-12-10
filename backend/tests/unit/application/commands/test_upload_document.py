"""Tests for UploadDocumentHandler."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.application.commands.upload_document import (
    UploadDocumentCommand,
    UploadDocumentHandler,
)


class StubJobCreator:
    def __init__(self, job):
        self.job = job
        self.called_with: tuple[Path, str] | None = None

    def __call__(self, file_path: Path, filename: str):
        self.called_with = (file_path, filename)
        return self.job


def make_job(job_id: str) -> SimpleNamespace:
    status = SimpleNamespace(job_id=job_id)
    return SimpleNamespace(status=status)


def test_handle_returns_created_job(tmp_path: Path):
    uploaded_file = tmp_path / "document.pdf"
    uploaded_file.write_bytes(b"content")

    job = make_job("job-123")
    creator = StubJobCreator(job)
    handler = UploadDocumentHandler(creator)

    command = UploadDocumentCommand(file_path=uploaded_file, filename="document.pdf")
    result = handler.handle(command)

    assert result is job
    assert creator.called_with == (uploaded_file, "document.pdf")


def test_handle_raises_when_file_missing(tmp_path: Path):
    missing = tmp_path / "missing.pdf"
    handler = UploadDocumentHandler(lambda *_: make_job("job"))

    command = UploadDocumentCommand(file_path=missing, filename="missing.pdf")
    with pytest.raises(FileNotFoundError):
        handler.handle(command)
