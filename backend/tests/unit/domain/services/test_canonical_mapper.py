"""Unit tests for the CanonicalMapper domain service (policy conversion)."""
from __future__ import annotations

import pytest

from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.services.canonical_mapper import CanonicalMapper
from backend.domain.value_objects import CanonicalFieldIndex


@pytest.fixture()
def mapper() -> CanonicalMapper:
    return CanonicalMapper(schema_version="test-1.0.0")


def make_field(
    name: str,
    value: str,
    *,
    confidence: float = 0.95,
    page_number: int = 1,
) -> FieldExtraction:
    return FieldExtraction.create(
        field_name=name,
        value=value,
        field_type="text",
        confidence=confidence,
        page_number=page_number,
    )


def test_build_empty_bundle_includes_policy_conversion(mapper: CanonicalMapper) -> None:
    bundle = mapper.build_empty_bundle()

    assert bundle["schemaVersion"] == "test-1.0.0"
    assert "policyConversion" in bundle
    assert len(bundle["policyConversion"]) == 60
    assert bundle["documentTypes"] == ["policy_conversion"]
    assert bundle["documentCategories"] == ["policy_conversion"]


def test_map_document_populates_from_extraction(mapper: CanonicalMapper) -> None:
    benefit_type = make_field("Benefit Type", "Comprehensive", confidence=0.82)
    max_benefit = make_field("Maximum Lifetime $Benefit", "$250,000", confidence=0.73, page_number=2)

    page = PageExtraction.create(page_number=2, fields=[benefit_type, max_benefit], tables=[])
    bundle = mapper.map_document([page])

    entry = bundle["policyConversion"]["Benefit Type"]
    assert entry["value"] == "Comprehensive"
    assert entry["sources"][0]["page"] == 2

    max_entry = bundle["policyConversion"]["Maximum Lifetime $Benefit"]
    assert max_entry["value"] == "$250,000"
    assert max_entry["sources"][0]["page"] == 2


def test_map_document_prefers_search_hits(mapper: CanonicalMapper) -> None:
    page = PageExtraction.create(page_number=1, fields=[], tables=[])
    hits = {
        "BENEFIT_TYPE": [
            {"text": "Home Care Only", "score": 0.9, "page": 1},
        ]
    }
    bundle = mapper.map_document([page], search_hits=hits)
    entry = bundle["policyConversion"]["Benefit Type"]
    assert entry["value"] == "Home Care Only"
    assert entry["confidence"] == 0.9
    assert entry["sources"][0]["snippet"] == "Home Care Only"


def test_canonical_field_order_matches_index() -> None:
    ordered_labels = CanonicalFieldIndex.ordered_labels()
    assert ordered_labels[0] == "Benefit Type"
    assert ordered_labels[-1].startswith("Additional Benefits")
