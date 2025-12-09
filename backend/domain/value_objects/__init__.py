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
    GENERAL_INVOICE_CORE_FIELDS,
    GENERAL_INVOICE_LINE_ITEM_FIELDS,
    GENERAL_INVOICE_FIELDS,
    UB04_LINE_ITEM_ATTRIBUTES,
    CMR_FIELDS,
    UB04_FIELDS,
    ALL_CANONICAL_FIELDS,
    canonical_field_labels,
)
from .identity_block import IdentityBlock

__all__ = [
    'Confidence',
    'BoundingBox',
    'JobState',
    'JobStatus',
    'CanonicalField',
    'CanonicalGroup',
    'CanonicalFieldIndex',
    'GENERAL_INVOICE_CORE_FIELDS',
    'GENERAL_INVOICE_LINE_ITEM_FIELDS',
    'GENERAL_INVOICE_FIELDS',
    'UB04_LINE_ITEM_ATTRIBUTES',
    'CMR_FIELDS',
    'UB04_FIELDS',
    'ALL_CANONICAL_FIELDS',
    'canonical_field_labels',
    'IdentityBlock',
]
