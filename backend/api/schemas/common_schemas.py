"""
Common schemas shared across different API endpoints
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class BoundingBoxSchema(BaseModel):
    x: float
    y: float
    width: float
    height: float
