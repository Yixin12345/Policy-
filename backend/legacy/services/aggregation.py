from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Dict, List

from ...models.job import ExtractionJob, FieldExtraction


def aggregate_fields(job: ExtractionJob) -> Dict[str, Any]:
  bucket: Dict[str, List[FieldExtraction]] = defaultdict(list)
  for page in job.pages:
    for field in page.fields:
      key = field.name.strip().lower()
      bucket[key].append(field)

  aggregated = []
  for key, fields in bucket.items():
    pages = sorted({f.page for f in fields})
    best = max(fields, key=lambda item: item.confidence if item.confidence is not None else 0.0)
    confidences = [f.confidence for f in fields if f.confidence is not None]
    stats = {
      "min": min(confidences) if confidences else 0.0,
      "max": max(confidences) if confidences else 0.0,
      "avg": mean(confidences) if confidences else 0.0,
    }
    aggregated.append(
      {
        "canonicalName": best.name,
        "pages": pages,
        "values": [
          {"page": f.page, "value": f.value, "confidence": f.confidence}
          for f in fields
        ],
        "bestValue": best.value,
        "confidenceStats": stats,
      }
    )

  return {"jobId": job.status.job_id, "fields": aggregated}
