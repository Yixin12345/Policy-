"""Upload endpoints for v1 API."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from backend.api.schemas import UploadResponseSchema
from backend.api.v1.dependencies import (
    get_job_starter,
    get_upload_document_handler,
)
from backend.application.commands.upload_document import (
    UploadDocumentCommand,
    UploadDocumentHandler,
)

router = APIRouter(tags=["uploads"])


@router.post("/upload", response_model=UploadResponseSchema, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    handler: UploadDocumentHandler = Depends(get_upload_document_handler),
    job_starter=Depends(get_job_starter),
) -> UploadResponseSchema:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".md", ".mmd"}:
        raise HTTPException(status_code=400, detail="Only PDF or Markdown files are supported")

    media_type = "markdown" if suffix in {".md", ".mmd"} else "pdf"

    base_dir = Path("backend_data")
    base_dir.mkdir(exist_ok=True)
    temp_pdf_path = base_dir / file.filename
    with temp_pdf_path.open("wb") as buffer:
        data = await file.read()
        buffer.write(data)

    try:
        job = handler.handle(
            UploadDocumentCommand(
                file_path=temp_pdf_path,
                filename=file.filename,
                media_type=media_type,
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        temp_pdf_path.unlink(missing_ok=True)

    background_tasks.add_task(job_starter, job)
    return UploadResponseSchema(jobId=job.status.job_id)
