from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_STORAGE_DIR = Path("backend_data")
SNAPSHOT_FILENAME = "job_snapshot.json"


def _ensure_storage_dir() -> None:
  BASE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _job_dir(job_id: str) -> Path:
  return BASE_STORAGE_DIR / job_id


def _snapshot_path(job_id: str) -> Path:
  return _job_dir(job_id) / SNAPSHOT_FILENAME


def save_snapshot_payload(job_id: str, payload: Dict[str, Any]) -> None:
  """Persist a prepared snapshot payload to disk."""
  try:
    _ensure_storage_dir()
    job_dir = _job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = _snapshot_path(job_id)
    snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
  except Exception as exc:  # pragma: no cover - persistence best effort
    logger.exception("Failed to save snapshot for %s: %s", job_id, exc)


def load_snapshot(job_id: str) -> Optional[Dict[str, Any]]:
  snapshot_path = _snapshot_path(job_id)
  if not snapshot_path.exists():
    return None
  try:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return data
  except json.JSONDecodeError as exc:
    logger.error("Snapshot %s invalid JSON: %s", job_id, exc)
    return None


def list_snapshot_raw() -> List[Dict[str, Any]]:
  _ensure_storage_dir()
  results: List[Dict[str, Any]] = []
  for job_dir in BASE_STORAGE_DIR.iterdir():
    if not job_dir.is_dir():
      continue
    snapshot_path = job_dir / SNAPSHOT_FILENAME
    if not snapshot_path.exists():
      continue
    try:
      data = json.loads(snapshot_path.read_text(encoding="utf-8"))
      results.append(data)
    except Exception as exc:  # pragma: no cover
      logger.debug("Skipping snapshot %s due to error: %s", snapshot_path, exc)
  return results
