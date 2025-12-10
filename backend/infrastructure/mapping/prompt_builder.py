"""Construct canonical mapping prompts for Policy Conversion (60 fields)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from backend.domain.value_objects.canonical_field import CanonicalFieldIndex


@dataclass(frozen=True)
class PromptBundle:
    """Container for the generated prompt components."""

    system_prompt: str
    instructions: str
    schema_summary: str
    output_schema: str
    search_context: str


class CanonicalPromptBuilder:
    """Assemble prompts for policy conversion mapping."""

    def __init__(self, *, schema_version: str = "2025-12-10") -> None:
        self._schema_version = schema_version

    def build(
        self,
        *,
        search_snippets: Dict[str, List[dict]] | None = None,
    ) -> PromptBundle:
        schema_summary = self._render_schema_summary()
        instructions = self._render_instructions()
        output_schema = self._render_output_schema()
        system_prompt = self._render_system_prompt()
        search_context = self._render_search_context(search_snippets or {})
        return PromptBundle(
            system_prompt=system_prompt,
            instructions=instructions,
            schema_summary=schema_summary,
            output_schema=output_schema,
            search_context=search_context,
        )

    def _render_system_prompt(self) -> str:
        lines = [
            "You are an illumifin policy conversion mapping assistant.",
            "Transform OCR/JSON extraction plus Azure Search snippets into the canonical 60-field policy conversion schema.",
            "Respond with strict JSON matching the output schema.",
            "Mark missing fields as null and include sources and confidence for every populated value.",
        ]
        return "\n".join(lines)

    def _render_instructions(self) -> str:
        lines: List[str] = [
            f"Schema version: {self._schema_version}.",
            "Rules:",
            "1. Populate a field only when evidence exists in extraction JSON or search snippets.",
            "2. Include sources: page, fieldId/tableId when available, and copied search snippet text.",
            "3. Provide confidence for each value; use lower confidence when evidence is weak.",
            "4. If no evidence, set the value to null and do not fabricate data.",
            "5. Preserve provided skeleton values; only overwrite when new evidence is stronger.",
        ]
        return "\n".join(lines)

    def _render_output_schema(self) -> str:
        lines = [
            "Return strict JSON with keys:",
            "- schemaVersion: string",
            "- generatedAt: ISO8601 UTC timestamp",
            "- documentTypes: array, must include \"policy_conversion\"",
            "- documentCategories: array, must include \"policy_conversion\"",
            "- policyConversion: object with exactly the 60 field labels shown in the schema summary; each value is",
            "  {\"value\": string|null, \"confidence\": number|null, \"sources\": [{\"page\": int optional, \"fieldId\": string optional, \"tableId\": string optional, \"column\": int optional, \"snippet\": string optional}] }",
            "- sourceMap: object keyed by canonical identifiers with source metadata (page, confidence, snippet).",
            "- reasoningNotes: array of strings for any assumptions or low-confidence areas.",
        ]
        return "\n".join(lines)

    def _render_schema_summary(self) -> str:
        lines: List[str] = ["Policy Conversion Fields (60):"]
        for field in CanonicalFieldIndex.ordered():
            lines.append(f"- {field.label}: {field.description}")
        return "\n".join(lines)

    def _render_search_context(self, snippets: Dict[str, List[dict]]) -> str:
        if not snippets:
            return "No Azure Search snippets were available."
        lines: List[str] = ["Azure Search snippets (top matches per field):"]
        for identifier, hits in snippets.items():
            try:
                field = CanonicalFieldIndex.by_identifier(identifier)
            except KeyError:
                continue
            lines.append(f"- {field.label}:")
            for hit in hits:
                score = hit.get("score")
                text = (hit.get("text") or "").strip()
                page = hit.get("page")
                lines.append(f"  • score={score}, page={page}, text=\"{text}\"")
        return "\n".join(lines)
