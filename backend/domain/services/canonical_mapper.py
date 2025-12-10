"""Canonical mapping domain service for policy conversion benefits.

Builds a canonical bundle skeleton with the 60 policy-conversion fields
and optionally seeds values from extraction hits (e.g., Azure Search).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from backend.domain.value_objects.canonical_field import (
    ALL_CANONICAL_FIELDS,
    CanonicalField,
    CanonicalFieldIndex,
    CanonicalGroup,
)


@dataclass(frozen=True)
class CanonicalSource:
    """Source metadata for a canonical value."""

    page: int | None = None
    field_ids: Sequence[str] = field(default_factory=tuple)
    table_id: str | None = None
    column: int | None = None
    confidence: float | None = None
    snippet: str | None = None


@dataclass
class CanonicalValue:
    """Canonical value container with metadata."""

    label: str
    value: str | None = None
    confidence: float | None = None
    sources: list[CanonicalSource] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "value": self.value,
            "confidence": self.confidence,
            "sources": [source.__dict__ for source in self.sources],
        }


class CanonicalMapper:
    """Builds canonical bundles from extracted document data."""

    def __init__(self, schema_version: str = "1.0.0", default_low_confidence: float = 0.35) -> None:
        self._schema_version = schema_version
        self._default_low_confidence = default_low_confidence
        self._label_lookup = self._build_label_lookup()

    @property
    def schema_version(self) -> str:
        return self._schema_version

    def build_empty_bundle(self) -> dict:
        """Return a skeleton bundle with all policy conversion fields set to null."""

        policy_conversion = {
            field.label: None for field in CanonicalFieldIndex.ordered()
        }
        return {
            "schemaVersion": self._schema_version,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "policyConversion": policy_conversion,
            "documentTypes": ["policy_conversion"],
            "documentCategories": ["policy_conversion"],
            "sourceMap": {},
        }

    def map_document(
        self,
        pages: Sequence["PageExtraction"],
        search_hits: Mapping[str, Sequence[dict]] | None = None,
    ) -> dict:
        """Build canonical bundle from extracted pages and optional search hits."""

        # Lazy import to avoid circular dependency
        from backend.domain.entities.page_extraction import PageExtraction

        bundle = self.build_empty_bundle()
        source_map: Dict[str, dict] = {}

        # Seed from search hits (preferred)
        if search_hits:
            for identifier, hits in search_hits.items():
                try:
                    field = CanonicalFieldIndex.by_identifier(identifier)
                except KeyError:
                    continue
                best = hits[0] if hits else None
                if not best:
                    continue
                bundle["policyConversion"][field.label] = {
                    "value": best.get("text") or best.get("value"),
                    "confidence": best.get("score"),
                    "sources": [
                        {
                            "page": best.get("page"),
                            "fieldId": best.get("field_id"),
                            "tableId": best.get("table_id"),
                            "column": best.get("column"),
                            "snippet": best.get("text"),
                        }
                    ],
                }
                source_map[field.identifier] = {
                    "page": best.get("page"),
                    "score": best.get("score"),
                    "snippet": best.get("text"),
                    "source": "azure_search",
                }

        # Seed from direct extraction when available and not already populated
        for page in pages:
            if not isinstance(page, PageExtraction):
                continue
            for field_extraction in page.fields:
                canonical_field = self._canonical_field_for_name(field_extraction.field_name)
                if canonical_field is None:
                    continue
                key = canonical_field.label
                existing = bundle["policyConversion"].get(key)
                if existing:
                    # Prefer existing (search or higher confidence) value
                    continue
                value = field_extraction.value or None
                confidence = getattr(field_extraction.confidence, "value", None) or self._default_low_confidence
                bundle["policyConversion"][key] = {
                    "value": value,
                    "confidence": confidence,
                    "sources": [
                        {
                            "page": page.page_number,
                            "fieldId": str(field_extraction.id),
                        }
                    ],
                }
                source_map[canonical_field.identifier] = {
                    "page": page.page_number,
                    "fieldId": str(field_extraction.id),
                    "confidence": confidence,
                    "source": "extraction",
                }

        bundle["sourceMap"] = source_map
        return bundle

    def _canonical_field_for_name(
        self,
        name: str | None,
    ) -> CanonicalField | None:
        """Match an extracted field name to a canonical field by fuzzy label."""

        if not name:
            return None
        normalized = name.strip().lower()
        if not normalized:
            return None
        return self._label_lookup.get(normalized)

    def _build_label_lookup(self) -> Dict[str, CanonicalField]:
        lookup: Dict[str, CanonicalField] = {}
        for field in ALL_CANONICAL_FIELDS:
            lookup[field.label.lower()] = field
        return lookup
