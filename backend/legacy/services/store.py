from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

from ...models.job import ExtractionJob


class JobStore:
  def __init__(self) -> None:
    self._jobs: Dict[str, ExtractionJob] = {}
    self._lock = Lock()

  def add(self, job: ExtractionJob) -> None:
    with self._lock:
      self._jobs[job.status.job_id] = job

  def get(self, job_id: str) -> Optional[ExtractionJob]:
    with self._lock:
      return self._jobs.get(job_id)

  def update(self, job_id: str, job: ExtractionJob) -> None:
    with self._lock:
      self._jobs[job_id] = job

  def list(self) -> List[ExtractionJob]:
    with self._lock:
      return list(self._jobs.values())

  def remove(self, job_id: str) -> None:
    with self._lock:
      self._jobs.pop(job_id, None)

  def ensure_dirs(self, base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)


job_store = JobStore()
