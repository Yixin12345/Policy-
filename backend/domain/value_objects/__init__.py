"""
Domain Value Objects

Immutable value objects that encapsulate domain concepts with validation.
"""
from .confidence import Confidence
from .bounding_box import BoundingBox
from .job_status import JobState, JobStatus
from .canonical_field import (
    CanonicalField,
    CanonicalGroup,
    CanonicalFieldIndex,
    ALL_CANONICAL_FIELDS,
    canonical_field_labels,
)

__all__ = [
    'Confidence',
    'BoundingBox',
    'JobState',
    'JobStatus',
    'CanonicalField',
    'CanonicalGroup',
    'CanonicalFieldIndex',
    'ALL_CANONICAL_FIELDS',
    'canonical_field_labels',
]
