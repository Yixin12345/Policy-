"""Pytest configuration for backend tests.

Ensures the project root is on sys.path so imports like ``backend.*`` and
``domain.*`` resolve during test collection. The legacy test suite expects a
"domain" top-level package; we provide that alias here while the codebase
transitions to the new clean architecture layout.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Add repository root to sys.path for module resolution.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure the "backend" package is importable and provide legacy aliases.
backend_pkg = importlib.import_module("backend")

# Legacy tests import from ``domain.*``; expose backend.domain under that name.
if "domain" not in sys.modules:
    sys.modules["domain"] = importlib.import_module("backend.domain")

# Provide shorter aliases mirroring historical structure if needed.
for alias, module_name in {
    "application": "backend.application",
    "infrastructure": "backend.infrastructure",
}.items():
    if alias not in sys.modules:
        sys.modules[alias] = importlib.import_module(module_name)
