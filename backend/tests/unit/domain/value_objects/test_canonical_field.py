"""Tests for canonical field metadata definitions."""
from __future__ import annotations

import pytest

from backend.domain.value_objects import (
    ALL_CANONICAL_FIELDS,
    CanonicalFieldIndex,
    CanonicalGroup,
)


def test_canonical_field_count_matches_spec() -> None:
    """Ensure the canonical field enumeration mirrors the 60 benefit attributes."""

    assert len(ALL_CANONICAL_FIELDS) == 60


def test_canonical_field_labels_are_ordered() -> None:
    """Canonical labels should be sorted by order and stable."""

    ordered = CanonicalFieldIndex.ordered()
    assert ordered[0].label == "Benefit Type"
    assert ordered[-1].label.startswith("Additional Benefits")


def test_single_group_defined() -> None:
    """Only the policy conversion group should be present."""

    assert set(CanonicalGroup) == {CanonicalGroup.POLICY_CONVERSION}
