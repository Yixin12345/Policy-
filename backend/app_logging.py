from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Mapping


class JsonFormatter(logging.Formatter):
  def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
    payload: dict[str, Any] = {
      "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
      "level": record.levelname,
      "logger": record.name,
      "message": record.getMessage(),
    }
    if record.exc_info:
      payload["exc_info"] = self.formatException(record.exc_info)
    for key, value in getattr(record, "__dict__", {}).items():
      if key.startswith("_"):
        continue
      if key in payload:
        continue
      if isinstance(value, (str, int, float, bool)) or value is None:
        payload[key] = value
    return json.dumps(payload, ensure_ascii=False)


def _log_level() -> str:
  return os.getenv("LOG_LEVEL", "INFO").upper()


def configure_logging(structured: bool = True) -> None:
  root = logging.getLogger()
  for handler in list(root.handlers):  # reset existing handlers
    root.removeHandler(handler)

  root.setLevel(_log_level())
  stream_handler = logging.StreamHandler(sys.stdout)
  if structured:
    stream_handler.setFormatter(JsonFormatter())
  else:
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
  root.addHandler(stream_handler)

  # Reduce noisy third-party loggers if present.
  logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
  logging.getLogger("openai").setLevel(logging.INFO)
