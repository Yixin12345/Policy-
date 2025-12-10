from backend.infrastructure.mapping.prompt_builder import CanonicalPromptBuilder


def test_prompt_builder_renders_schema_and_search():
    builder = CanonicalPromptBuilder(schema_version="test-2025")
    bundle = builder.build(search_snippets={"BENEFIT_TYPE": [{"text": "Home Care Only", "score": 0.9, "page": 1}]})

    assert "Policy Conversion Fields" in bundle.schema_summary
    assert "Benefit Type" in bundle.schema_summary
    assert "policyConversion" in bundle.output_schema
    assert "Azure Search snippets" in bundle.search_context
    assert "Home Care Only" in bundle.search_context
