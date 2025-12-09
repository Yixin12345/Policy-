"""Construct canonical mapping prompts with schema guidance."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Set, Tuple

from backend.domain.value_objects.canonical_field import CanonicalFieldIndex, CanonicalGroup


@dataclass(frozen=True)
class PromptBundle:
    """Container for the generated prompt components."""

    system_prompt: str
    instructions: str
    schema_summary: str
    output_schema: str


_GROUP_METADATA: Dict[CanonicalGroup, Dict[str, str]] = {
    CanonicalGroup.GENERAL_INVOICE: {
        "title": "General Invoice",
        "document_category": "facility_invoice",
    },
    CanonicalGroup.CMR: {
        "title": "Continued Monthly Residence (CMR) Form",
        "document_category": "cmr_form",
    },
    CanonicalGroup.UB04: {
        "title": "UB04 Institutional Claim",
        "document_category": "ub04",
    },
}

_DOCUMENT_CATEGORY_TO_GROUP: Dict[str, CanonicalGroup] = {
    meta["document_category"]: group for group, meta in _GROUP_METADATA.items()
}


class CanonicalPromptBuilder:
    """Assemble prompts that keep mappings scoped to the correct documents."""

    def __init__(self, *, schema_version: str = "2025-11-20") -> None:
        self._schema_version = schema_version

    def build(
        self,
        *,
        document_categories: Sequence[str] | None = None,
        page_categories: Dict[int, str] | None = None,
    ) -> PromptBundle:
        """Generate the structured prompt bundle for the mapping request."""

        normalized_doc_categories = self._normalize_categories(document_categories)
        normalized_page_categories = self._normalize_page_categories(page_categories)
        groups = self._groups_in_scope(normalized_doc_categories, normalized_page_categories)
        schema_summary = self._render_schema_summary(groups)
        instructions = self._render_instructions(
            normalized_doc_categories,
            normalized_page_categories,
            groups,
        )
        output_schema = self._render_output_schema(groups)
        system_prompt = self._render_system_prompt()
        return PromptBundle(
            system_prompt=system_prompt,
            instructions=instructions,
            schema_summary=schema_summary,
            output_schema=output_schema,
        )

    def _render_system_prompt(self) -> str:
        lines = [
            "You are an illumifin claims data mapping assistant.",
            "Transform OCR extraction JSON into the canonical schema while preserving provenance and confidence metadata.",
            "Respond with strict JSON that matches the canonical response schema.",
            "Leave values null when evidence is missing and never fabricate sources.",
        ]
        return "\n".join(lines)

    def _render_instructions(
        self,
        document_categories: Sequence[str],
        page_categories: Dict[int, str],
        groups: Sequence[CanonicalGroup],
    ) -> str:
        lines: List[str] = [
            f"Schema version: {self._schema_version}.",
            "Follow these rules:",
            "1. Only populate canonical fields when you find explicit evidence on the indicated pages.",
            "2. Do not copy values across document categories; each field must come from pages matching its category.",
            "3. Include source references using the provided fieldId or tableId plus page number.",
            "4. Provide short notes when confidence is low or evidence is ambiguous.",
            "5. Never overwrite high-confidence deterministic values if a skeleton is provided; only fill in missing or low-confidence fields.",
        ]

        if document_categories:
            lines.append(
                "Document categories in scope: "
                + ", ".join(sorted(document_categories))
                + "."
            )
        else:
            lines.append("Document categories were not pre-classified; infer them from the evidence.")

        if page_categories:
            lines.append("Page category hints:")
            for page_number in sorted(page_categories):
                category = page_categories[page_number]
                lines.append(f"- Page {page_number}: {category}")

        lines.append(
            "Restricted field groups: "
            + ", ".join(_GROUP_METADATA[group]["title"] for group in groups)
            + "."
        )

        return "\n".join(lines)

    def _render_output_schema(self, groups: Sequence[CanonicalGroup]) -> str:
        canonical_groups = ", ".join(_GROUP_METADATA[group]["document_category"] for group in groups)
        lines = [
            "Return strict JSON with this structure:",
            "- schemaVersion: string (reuse the provided schema version).",
            "- generatedAt: ISO8601 UTC timestamp.",
            "- documentCategories: array of uppercase category codes that apply (e.g., INVOICE, CMR, UB04).",
            "- documentTypes: array of inferred document types (facility_invoice, cmr_form, ub04).",
            "- invoice / cmr / ub04: objects keyed by the exact field labels listed in the schema summary.",
            "  Each field value must be an object {\"value\": string|null, \"confidence\": number|null, \"sources\": [{\"page\": int optional, \"fieldId\": string optional, \"tableId\": string optional, \"column\": int optional}]}.",
            "- invoiceLineItems: array of facility invoice line item objects (Fields 10–18). Each item should include description, startDate, endDate, unitType, unitQuantity, chargesAmount, balance, totalDue, and credits as canonical value objects with provenance metadata.",
            "- identityBlocks: array of identity block objects with keys blockType, sequence, policyNumber, policyholderName, policyholderAddress, providerName, providerAddress, patientName, patientAddress, birthDate, typeOfBill, fedTaxNo, statementPeriod, presentFields[], and source {page, fieldIds}.",
            "- reasoningNotes: array of short strings explaining uncertainties or assumptions.",
            "- sourceMap: object keyed by canonical identifiers (e.g., POLICY_NUMBER) mapping to provenance summaries (pages, fieldIds, tableIds, columns, confidenceAggregate).",
        ]
        if groups:
            lines.append(f"Active canonical groups: {canonical_groups}.")
        return "\n".join(lines)

    def _render_schema_summary(self, groups: Sequence[CanonicalGroup]) -> str:
        sections: List[str] = []
        for group in groups:
            metadata = _GROUP_METADATA[group]
            header = f"{metadata['title']} (document category: {metadata['document_category']})"
            fields = CanonicalFieldIndex.for_group(group)
            regular_fields = [field for field in fields if field.include_in_group]
            line_item_fields = [field for field in fields if not field.include_in_group and field.line_item_attribute]
            field_lines = [
                f"- {field.identifier}: {field.label} — {field.description}" for field in regular_fields
            ]
            if line_item_fields:
                field_lines.append("- Invoice line items (Fields 10–18): repeatable entries with these attributes:")
                for field in sorted(line_item_fields, key=lambda item: item.order):
                    field_lines.append(
                        f"  - {field.identifier}: {field.label} — {field.description}"
                    )
            sections.append("\n".join([header, *field_lines]))
        return "\n\n".join(sections)

    def _groups_in_scope(
        self,
        document_categories: Sequence[str],
        page_categories: Dict[int, str],
    ) -> Tuple[CanonicalGroup, ...]:
        in_scope: Set[CanonicalGroup] = set()

        for category in document_categories:
            if category in _DOCUMENT_CATEGORY_TO_GROUP:
                in_scope.add(_DOCUMENT_CATEGORY_TO_GROUP[category])

        for category in page_categories.values():
            if category in _DOCUMENT_CATEGORY_TO_GROUP:
                in_scope.add(_DOCUMENT_CATEGORY_TO_GROUP[category])

        if not in_scope:
            in_scope = set(_GROUP_METADATA.keys())

        ordered_groups = [
            group
            for group in _GROUP_METADATA.keys()
            if group in in_scope
        ]
        return tuple(ordered_groups)

    def _normalize_categories(self, categories: Sequence[str] | None) -> Tuple[str, ...]:
        if not categories:
            return tuple()
        seen: Set[str] = set()
        ordered: List[str] = []
        for category in categories:
            normalized = category.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return tuple(ordered)

    def _normalize_page_categories(
        self, page_categories: Dict[int, str] | None
    ) -> Dict[int, str]:
        if not page_categories:
            return {}
        normalized: Dict[int, str] = {}
        for raw_page, raw_category in page_categories.items():
            if raw_category is None:
                continue
            normalized[int(raw_page)] = raw_category.strip().lower()
        return normalized

