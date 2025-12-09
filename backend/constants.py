from __future__ import annotations

# Single source of truth for static constants and versions.

SNAPSHOT_VERSION = 1

# Confidence quantization steps for OCR extraction.
CONFIDENCE_STEPS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

# Table grouping heuristic thresholds.
TABLE_WIDTH_RATIO_MIN = 0.65
TABLE_WIDTH_RATIO_MAX = 1.35
HEADER_SIMILARITY_MIN = 0.6
