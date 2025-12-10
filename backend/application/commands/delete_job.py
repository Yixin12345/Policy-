"""DeleteJob Command - Removes a job and its associated data.

Validates the job is in a deletable state (not running) then removes snapshot.
"""
from dataclasses import dataclass
from typing import Dict, Any

from backend.domain.repositories.job_repository import JobRepository
from backend.domain.exceptions import EntityNotFoundError, EntityValidationError
from backend.domain.value_objects.job_status import JobStatus, JobState


@dataclass(frozen=True)
class DeleteJobCommand:
    job_id: str


class DeleteJobHandler:
    """Handles DeleteJob commands."""

    def __init__(self, job_repository: JobRepository):
        self._jobs = job_repository

    def handle(self, command: DeleteJobCommand) -> Dict[str, Any]:
        job = self._jobs.find_by_id(command.job_id)
        if job is None:
            raise EntityNotFoundError("Job", command.job_id)
        # Only block deletion of actively running jobs
        if job.status.state in [JobState.RUNNING]:
            raise EntityValidationError(
                "Job",
                {"status": f"Cannot delete job {command.job_id} with status {job.status.state.value}"}
            )
        self._jobs.delete(command.job_id)
        return {"job_id": command.job_id, "deleted": True}
