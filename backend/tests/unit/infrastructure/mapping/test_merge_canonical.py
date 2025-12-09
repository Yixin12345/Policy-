"""Tests for canonical bundle merge utility."""
from collections import OrderedDict

from backend.infrastructure.mapping.azure_mapping_client import merge_canonical_bundles


def test_merge_canonical_bundles_preserves_deterministic_values() -> None:
    deterministic = {
        "schemaVersion": "1.0.0",
        "generatedAt": "2025-01-01T00:00:00Z",
        "documentCategories": ["INVOICE"],
        "invoice": OrderedDict(
            {
                "Invoice number": {
                    "value": "INV-123",
                    "confidence": 0.95,
                    "sources": [{"fieldId": "f1"}],
                }
            }
        ),
        "cmr": OrderedDict(
            {
                "Policy number": {
                    "value": None,
                    "confidence": None,
                    "sources": [],
                }
            }
        ),
        "ub04": OrderedDict(),
        "identityBlocks": [],
        "reasoningNotes": [],
        "sourceMap": {},
    }

    llm = {
        "documentCategories": ["INVOICE", "UB04"],
        "documentTypes": ["facility_invoice"],
        "invoice": {
            "Invoice number": {
                "value": "INV-999",
                "confidence": 0.6,
                "sources": [{"fieldId": "f2"}],
            }
        },
        "cmr": {
            "Policy number": {
                "value": "CMR-123",
                "confidence": 0.7,
                "sources": [{"fieldId": "f3"}],
            }
        },
        "reasoningNotes": ["Missing UB04 line items"],
    }

    merged = merge_canonical_bundles(deterministic, llm)

    invoice_entry = merged["invoice"]["Invoice number"]
    assert invoice_entry["value"] == "INV-123"
    assert invoice_entry["confidence"] == 0.95
    assert {"fieldId": "f1"} in invoice_entry["sources"]
    assert {"fieldId": "f2"} in invoice_entry["sources"]

    cmr_entry = merged["cmr"]["Policy number"]
    assert cmr_entry["value"] == "CMR-123"
    assert cmr_entry["confidence"] == 0.7

    assert merged["documentCategories"] == ["INVOICE", "UB04"]
    assert merged["documentTypes"] == ["facility_invoice"]
    assert merged["reasoningNotes"] == ["Missing UB04 line items"]
