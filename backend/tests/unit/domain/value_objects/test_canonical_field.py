"""Tests for canonical field metadata definitions."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.domain.value_objects import (
    ALL_CANONICAL_FIELDS,
    CanonicalFieldIndex,
    CanonicalGroup,
)


@pytest.fixture()
def required_field_labels() -> list[str]:
    """Parse `RequiredFields.md` and extract the bolded labels."""

    spec_path = Path("RequiredFields.md")
    if not spec_path.exists():
        raise RuntimeError("RequiredFields.md not found in repository root")

    pattern = re.compile(r"^(?:\d+\.|-)\s+\*\*(.+?)\*\*", re.MULTILINE)
    labels = pattern.findall(spec_path.read_text(encoding="utf-8"))
    return labels


def test_canonical_field_count_matches_spec(required_field_labels: list[str]) -> None:
    """Ensure the canonical field enumeration mirrors the spec count."""

    assert len(ALL_CANONICAL_FIELDS) == len(required_field_labels)


def test_canonical_field_labels_match_spec(required_field_labels: list[str]) -> None:
    """Canonical labels must appear in the same order as the specification."""

    assert CanonicalFieldIndex.ordered_labels() == required_field_labels


@pytest.mark.parametrize(
    "group",
    [
        CanonicalGroup.GENERAL_INVOICE,
        CanonicalGroup.CMR,
        CanonicalGroup.UB04,
    ],
)
def test_group_order_excludes_identity_members(group: CanonicalGroup) -> None:
    """Group label ordering should omit identity block-only fields."""

    group_labels = [
        field.label
        for field in CanonicalFieldIndex.for_group(group)
        if not field.is_identity_block_member and field.include_in_group
    ]
    section = CanonicalFieldIndex.for_group(group)
    expected_labels = [
        field.label
        for field in sorted(section, key=lambda f: f.order)
        if not field.is_identity_block_member and field.include_in_group
    ]
    assert group_labels == expected_labels


def test_identity_block_fields_are_flagged() -> None:
    """Identity block subset should all be marked as identity members."""

    identity_fields = CanonicalFieldIndex.identity_block_fields()
    assert identity_fields, "Expected at least one identity block field"
    assert all(field.is_identity_block_member for field in identity_fields)
