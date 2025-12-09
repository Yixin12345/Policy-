"""Tests for the canonical prompt builder."""
from backend.infrastructure.mapping.prompt_builder import CanonicalPromptBuilder


def test_prompt_builder_includes_descriptions_and_categories() -> None:
    builder = CanonicalPromptBuilder(schema_version="test-version")

    bundle = builder.build(
        document_categories=["facility_invoice", "ub04"],
        page_categories={1: "facility_invoice", 2: "ub04"},
    )

    assert "illumifin claims data mapping assistant" in bundle.system_prompt
    assert "Schema version: test-version." in bundle.instructions
    assert "facility_invoice" in bundle.instructions
    assert "Page 1: facility_invoice" in bundle.instructions
    assert "Restricted field groups: General Invoice, UB04 Institutional Claim." in bundle.instructions
    assert "POLICY_NUMBER" in bundle.schema_summary
    assert "Unique LTC policy identifier" in bundle.schema_summary
    assert "UB04_PROVIDER_NAME" in bundle.schema_summary
    assert "invoice / cmr / ub04" in bundle.output_schema
    assert "identity block objects" in bundle.output_schema


def test_prompt_builder_defaults_to_all_groups_when_unknown() -> None:
    builder = CanonicalPromptBuilder(schema_version="test-version")

    bundle = builder.build(document_categories=[], page_categories={})

    assert "General Invoice" in bundle.schema_summary
    assert "Continued Monthly Residence (CMR) Form" in bundle.schema_summary
    assert "UB04 Institutional Claim" in bundle.schema_summary
    assert "Document categories were not pre-classified" in bundle.instructions
    assert "Active canonical groups" in bundle.output_schema
