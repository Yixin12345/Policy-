"""Canonical mapping domain service.

Responsible for constructing the canonical bundle skeleton based on the
field definitions in `canonical_field.py`. Mapping logic that assigns
values will be layered on top of this scaffold in subsequent steps.
"""
from __future__ import annotations

from collections import OrderedDict
from statistics import mean
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple

from backend.domain.value_objects import (
    ALL_CANONICAL_FIELDS,
    CanonicalField,
    CanonicalFieldIndex,
    CanonicalGroup,
    GENERAL_INVOICE_LINE_ITEM_FIELDS,
    IdentityBlock,
)


IDENTITY_ATTRIBUTE_MAP: Dict[str, str] = {
    "CMR_POLICY_NUMBER_DUPLICATE": "policy_number",
    "CMR_POLICYHOLDER_NAME_DUPLICATE": "policyholder_name",
    "CMR_POLICYHOLDER_ADDRESS_DUPLICATE": "policyholder_address",
    "CMR_PROVIDER_NAME_DUPLICATE": "provider_name",
    "UB04_PROVIDER_NAME_DUPLICATE": "provider_name",
    "UB04_PROVIDER_ADDRESS_DUPLICATE": "provider_address",
    "TYPE_OF_BILL_DUPLICATE": "type_of_bill",
    "FED_TAX_NO_DUPLICATE": "fed_tax_no",
    "STATEMENT_PERIOD_DUPLICATE": "statement_period",
    "PATIENT_NAME_DUPLICATE": "patient_name",
    "PATIENT_ADDRESS_DUPLICATE": "patient_address",
    "BIRTH_DATE_DUPLICATE": "birth_date",
}

IDENTITY_BLOCK_TYPE_MAP: Dict[str, str] = {
    "CMR_POLICY_NUMBER_DUPLICATE": "policyHolderIdentity",
    "CMR_POLICYHOLDER_NAME_DUPLICATE": "policyHolderIdentity",
    "CMR_POLICYHOLDER_ADDRESS_DUPLICATE": "policyHolderIdentity",
    "CMR_PROVIDER_NAME_DUPLICATE": "providerIdentity",
    "UB04_PROVIDER_NAME_DUPLICATE": "providerIdentity",
    "UB04_PROVIDER_ADDRESS_DUPLICATE": "providerIdentity",
    "TYPE_OF_BILL_DUPLICATE": "providerIdentity",
    "FED_TAX_NO_DUPLICATE": "providerIdentity",
    "STATEMENT_PERIOD_DUPLICATE": "providerIdentity",
    "PATIENT_NAME_DUPLICATE": "patientIdentity",
    "PATIENT_ADDRESS_DUPLICATE": "patientIdentity",
    "BIRTH_DATE_DUPLICATE": "patientIdentity",
}

LINE_ITEM_HEADER_ALIASES: Dict[str, str] = {
    "revenue": "revenueCode",
    "rev": "revenueCode",
    "revcode": "revenueCode",
    "revenuecode": "revenueCode",
    "revenue code": "revenueCode",
    "description": "description",
    "item": "description",
    "detail": "description",
    "proc": "procedureCode",
    "procedure": "procedureCode",
    "procedure code": "procedureCode",
    "hcpcs": "procedureCode",
    "mod": "procedureModifier",
    "modifier": "procedureModifier",
    "service date": "serviceDate",
    "date of service": "serviceDate",
    "date": "serviceDate",
    "from": "serviceDateFrom",
    "to": "serviceDateTo",
    "units": "units",
    "qty": "units",
    "quantity": "units",
    "days": "units",
    "total charge": "totalCharge",
    "charges": "totalCharge",
    "charge": "totalCharge",
    "amount": "totalCharge",
    "rate": "rate",
}


@dataclass(frozen=True)
class CanonicalSource:
    """Source metadata for a canonical value."""

    page: int | None = None
    field_ids: Sequence[str] = field(default_factory=tuple)
    table_id: str | None = None
    column: int | None = None
    confidence: float | None = None


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

    def __init__(self, schema_version: str = "1.0.0", confidence_override: float = 0.92) -> None:
        self._schema_version = schema_version
        self._confidence_override = confidence_override
        self._label_lookup = self._build_label_lookup()
        self._invoice_line_item_identifiers = {
            field.identifier: field for field in GENERAL_INVOICE_LINE_ITEM_FIELDS
        }

    @property
    def schema_version(self) -> str:
        return self._schema_version

    def map_document(
        self,
        pages: Sequence["PageExtraction"],
        document_categories: Sequence[str] | None = None,
        page_categories: Mapping[int, Sequence[str]] | None = None,
    ) -> dict:
        """Build canonical bundle from extracted pages."""

        # Lazy import to avoid circular dependency at module level
        from backend.domain.entities.page_extraction import PageExtraction

        bundle = self.build_empty_bundle(document_categories)
        source_map: Dict[str, dict] = {}

        group_map: Dict[CanonicalGroup, MutableMapping[str, dict]] = {}
        if "invoice" in bundle:
            group_map[CanonicalGroup.GENERAL_INVOICE] = bundle["invoice"]
        if "cmr" in bundle:
            group_map[CanonicalGroup.CMR] = bundle["cmr"]
        if "ub04" in bundle:
            group_map[CanonicalGroup.UB04] = bundle["ub04"]

        identity_accumulator = _IdentityAccumulator()
        invoice_line_items = _InvoiceLineItemAccumulator()
        ub04_line_items: list[dict] = []

        for page in pages:
            if not isinstance(page, PageExtraction):
                continue
            allowed_groups = self._resolve_allowed_groups(
                page_categories.get(page.page_number) if page_categories else None
            )
            for field in page.fields:
                canonical_field = self._canonical_field_for_name(
                    field.field_name,
                    allowed_groups=allowed_groups,
                )
                if canonical_field is None:
                    continue
                if canonical_field.is_identity_block_member:
                    if canonical_field.group not in allowed_groups:
                        continue
                    identity_accumulator.add(
                        canonical_field=canonical_field,
                        value=field.value or None,
                        page_number=page.page_number,
                        field_id=str(field.id),
                    )
                    continue
                if canonical_field.identifier in self._invoice_line_item_identifiers:
                    line_item_field = self._invoice_line_item_identifiers[canonical_field.identifier]
                    invoice_line_items.add(
                        canonical_field=line_item_field,
                        raw_value=field.value or None,
                        confidence=field.confidence.value,
                        page_number=page.page_number,
                        field_name=field.field_name,
                        field_id=str(field.id),
                    )
                    self._record_source(
                        source_map,
                        line_item_field,
                        {
                            "page": page.page_number,
                            "fieldId": str(field.id),
                        },
                        field.confidence.value,
                    )
                    continue
                group = group_map.get(canonical_field.group)
                if group is None or canonical_field.label not in group:
                    continue
                value = field.value or None
                if canonical_field.identifier == "ABSENCE_DETAILS" and value:
                    value = self._normalize_absence_details(str(value))
                self._merge_value(
                    target=group,
                    label=canonical_field.label,
                    value=value,
                    confidence=field.confidence.value,
                    source={
                        "page": page.page_number,
                        "fieldId": str(field.id),
                    },
                    canonical_field=canonical_field,
                    source_map=source_map,
                )

            for table in page.tables:
                if CanonicalGroup.UB04 not in allowed_groups:
                    continue
                line_items_table = self._extract_line_items(table, page.page_number)
                if line_items_table is None:
                    continue
                canonical_field = CanonicalFieldIndex.by_label("Line items (Boxes 42–47)")
                ub04_line_items.append(line_items_table)
                table_confidence = line_items_table.get("confidence") if isinstance(line_items_table, dict) else None
                confidence_value = table_confidence if isinstance(table_confidence, (int, float)) else (
                    table.confidence.value if table.confidence else 0.0
                )
                self._record_source(
                    source_map,
                    canonical_field,
                    {
                        "page": page.page_number,
                        "tableId": str(table.id),
                    },
                    confidence_value,
                )

        bundle["identityBlocks"] = identity_accumulator.serialize()
        bundle["sourceMap"] = self._finalize_source_map(source_map)
        if "invoice" in bundle:
            bundle["invoiceLineItems"] = invoice_line_items.serialize()
        if "ub04" in bundle:
            bundle["ub04LineItems"] = ub04_line_items

        return bundle

    def build_empty_bundle(
        self,
        document_categories: Sequence[str] | None = None,
    ) -> dict:
        """Construct an ordered canonical bundle with null values."""

        categories = list(document_categories or [])
        now = datetime.now(timezone.utc).isoformat()

        bundle: dict = {
            "schemaVersion": self._schema_version,
            "generatedAt": now,
            "documentCategories": categories,
            "reasoningNotes": [],
            "identityBlocks": [],
            "sourceMap": {},
        }

        if self._should_include_group(categories, CanonicalGroup.GENERAL_INVOICE):
            bundle["invoice"] = self._empty_group(CanonicalGroup.GENERAL_INVOICE)
            bundle["invoiceLineItems"] = []
        if self._should_include_group(categories, CanonicalGroup.CMR):
            bundle["cmr"] = self._empty_group(CanonicalGroup.CMR)
        if self._should_include_group(categories, CanonicalGroup.UB04):
            bundle["ub04"] = self._empty_group(CanonicalGroup.UB04)
            bundle["ub04LineItems"] = []

        return bundle

    def _should_include_group(
        self, categories: Sequence[str], group: CanonicalGroup
    ) -> bool:
        """Determine if a group should be present in the bundle."""

        if not categories:
            return True
        keywords = {
            CanonicalGroup.GENERAL_INVOICE: ("INVOICE", "FACILITY", "GENERAL"),
            CanonicalGroup.CMR: ("CMR", "RESIDENCE", "MONTHLY"),
            CanonicalGroup.UB04: ("UB04", "UB-04", "CLAIM"),
        }
        tokens = keywords.get(group, tuple())
        if not tokens:
            return True
        normalized = [category.upper() for category in categories]
        return any(any(token in category for token in tokens) for category in normalized)

    def _empty_group(self, group: CanonicalGroup) -> OrderedDict[str, dict]:
        """Return ordered mapping of labels to empty canonical value dicts."""

        ordered_fields = sorted(
            (
                field
                for field in CanonicalFieldIndex.for_group(group)
                if not field.is_identity_block_member and field.include_in_group
            ),
            key=lambda f: f.order,
        )
        return OrderedDict(
            (field.label, {"value": None, "confidence": None, "sources": []})
            for field in ordered_fields
        )

    def seed_identity_blocks(self) -> list[IdentityBlock]:
        """Provide an empty identity block list preserving ordering metadata."""

        identity_fields: Iterable[CanonicalField] = CanonicalFieldIndex.identity_block_fields()
        if not identity_fields:
            return []

        # Group identity fields by logical block type based on label prefix.
        grouped: list[IdentityBlock] = []
        sequence = 1
        for field in identity_fields:
            block_type = self._infer_block_type(field)
            grouped.append(
                IdentityBlock(
                    block_type=block_type,
                    sequence=sequence,
                    present_fields=(field.identifier,),
                )
            )
            sequence += 1
        return grouped

    def _infer_block_type(self, field: CanonicalField) -> str:
        label_lower = field.label.lower()
        if "policyholder" in label_lower:
            return "policyHolderIdentity"
        if "provider" in label_lower:
            return "providerIdentity"
        if "patient" in label_lower:
            return "patientIdentity"
        return "identity"

    # ==================== Helpers ====================

    def _merge_value(
        self,
        target: MutableMapping[str, dict],
        label: str,
        value: object | None,
        confidence: float,
        source: Mapping[str, object],
        *,
        canonical_field: CanonicalField,
        source_map: Dict[str, dict],
    ) -> None:
        """Merge canonical value preferring higher confidence and aggregating sources."""

        entry = target.get(label) or {"value": None, "sources": []}
        existing_conf = entry.get("confidence")
        existing_val = entry.get("value")

        should_replace = False
        if existing_conf is None:
            should_replace = True
        elif confidence >= self._confidence_override:
            should_replace = True
        elif existing_conf is not None and confidence > existing_conf:
            should_replace = True
        elif existing_val in (None, "") and value not in (None, ""):
            should_replace = True

        if should_replace:
            entry.update({"value": value, "confidence": confidence})

        sources = list(entry.get("sources") or [])
        sources.append(dict(source))
        entry["sources"] = sources
        target[label] = entry
        self._record_source(source_map, canonical_field, source, confidence)

    def _build_label_lookup(self) -> Dict[str, list[CanonicalField]]:
        lookup: Dict[str, list[CanonicalField]] = {}
        for field in ALL_CANONICAL_FIELDS:
            self._append_lookup(lookup, self._sanitize(field.label), field)
            self._append_lookup(lookup, self._sanitize(field.identifier), field)
        # Manual alias augmentation for common raw field names
        manual_aliases = {
            "policy number": "Policy number",
            "policy_no": "Policy number",
            "policy no": "Policy number",
            "policyholder": "Policyholder name",
            "member name": "Policyholder name",
            "insured name": "Policyholder name",
            "insured address": "Policyholder address",
            "facility name": "Provider name",
            "facility address": "Provider address",
            "statement date": "Invoice date / statement date",
            "invoice date": "Invoice date / statement date",
            "tax id": "Tax ID",
            "ein": "Tax ID",
            "total due": "Total due / balance due",
            "balance due": "Total due / balance due",
            "balance amount": "Balance",
            "total amount due": "Total due / balance due",
            "provider tax id": "Tax ID",
            "start service date": "Start date",
            "end service date": "End date",
            "service start": "Start date",
            "service end": "End date",
            "units": "Unit / quantity",
            "unit": "Unit type",
            "absence details": "Absence details (if yes)",
            "absence_details": "Absence details (if yes)",
            "policy_number_duplicate": "Policy number (duplicate block)",
            "policy number duplicate": "Policy number (duplicate block)",
            "policyholder_name_duplicate": "Policyholder name (duplicate block)",
            "policyholder name duplicate": "Policyholder name (duplicate block)",
            "policyholder duplicate": "Policyholder name (duplicate block)",
            "policyholder address duplicate": "Policyholder address (duplicate block)",
            "provider_name_duplicate": "Provider name (duplicate block)",
            "provider name duplicate": "Provider name (duplicate block)",
            "provider address duplicate": "Provider address (duplicate, Box 1/2)",
            "type of bill duplicate": "Type of bill (duplicate, Box 4)",
            "type_of_bill_duplicate": "Type of bill (duplicate, Box 4)",
            "fed tax no duplicate": "Fed tax no (duplicate, Box 5)",
            "fed_tax_no_duplicate": "Fed tax no (duplicate, Box 5)",
            "statement period duplicate": "Statement period / service dates (duplicate, Box 6)",
            "statement_period_duplicate": "Statement period / service dates (duplicate, Box 6)",
            "patient_name_duplicate": "Patient name (duplicate, Box 8)",
            "patient address duplicate": "Patient address (duplicate, Box 9)",
            "patient_address_duplicate": "Patient address (duplicate, Box 9)",
            "birth_date_duplicate": "Birth date (duplicate, Box 10)",
        }
        for raw, label in manual_aliases.items():
            self._append_lookup(
                lookup,
                self._sanitize(raw),
                CanonicalFieldIndex.by_label(label),
            )
        return lookup

    def _append_lookup(
        self,
        lookup: Dict[str, list[CanonicalField]],
        key: str,
        field: CanonicalField,
    ) -> None:
        fields = lookup.setdefault(key, [])
        if field not in fields:
            fields.append(field)

    def _canonical_field_for_name(
        self,
        raw_name: str,
        *,
        allowed_groups: set[CanonicalGroup] | None = None,
    ) -> CanonicalField | None:
        sanitized = self._sanitize(raw_name)
        candidates = self._label_lookup.get(sanitized)
        if not candidates:
            return None
        if allowed_groups is None:
            return candidates[0]
        for field in candidates:
            if field.group in allowed_groups:
                return field
        return None

    @staticmethod
    def _sanitize(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def _resolve_allowed_groups(
        self,
        categories: Sequence[str] | None,
    ) -> set[CanonicalGroup]:
        if not categories:
            return {CanonicalGroup.GENERAL_INVOICE, CanonicalGroup.CMR, CanonicalGroup.UB04}
        allowed = {
            group
            for group in (CanonicalGroup.GENERAL_INVOICE, CanonicalGroup.CMR, CanonicalGroup.UB04)
            if self._categories_match_group(categories, group)
        }
        if not allowed:
            return {CanonicalGroup.GENERAL_INVOICE, CanonicalGroup.CMR, CanonicalGroup.UB04}
        return allowed

    def _categories_match_group(
        self,
        categories: Sequence[str],
        group: CanonicalGroup,
    ) -> bool:
        return self._should_include_group(categories, group)

    def _record_source(
        self,
        source_map: Dict[str, dict],
        canonical_field: CanonicalField,
        source: Mapping[str, object],
        confidence: float,
    ) -> None:
        entry = source_map.setdefault(
            canonical_field.identifier,
            {
                "pages": set(),
                "fieldIds": set(),
                "tableIds": set(),
                "columns": set(),
                "confidenceSamples": [],
            },
        )
        page = source.get("page")
        if page is not None:
            try:
                entry["pages"].add(int(page))
            except (TypeError, ValueError):  # pragma: no cover - defensive
                pass
        field_id = source.get("fieldId")
        if field_id is not None:
            entry["fieldIds"].add(str(field_id))
        table_id = source.get("tableId")
        if table_id is not None:
            entry["tableIds"].add(str(table_id))
        column = source.get("column")
        if column is not None:
            try:
                entry["columns"].add(int(column))
            except (TypeError, ValueError):  # pragma: no cover - defensive
                pass
        if isinstance(confidence, (int, float)):
            entry["confidenceSamples"].append(float(confidence))

    def _finalize_source_map(self, source_map: Dict[str, dict]) -> Dict[str, dict]:
        finalized: Dict[str, dict] = {}
        for identifier, raw_entry in source_map.items():
            pages = sorted(raw_entry.get("pages", set()))
            field_ids = sorted(raw_entry.get("fieldIds", set()))
            table_ids = sorted(raw_entry.get("tableIds", set()))
            columns = sorted(raw_entry.get("columns", set()))
            confidences = raw_entry.get("confidenceSamples", [])

            entry: Dict[str, object] = {}
            if pages:
                entry["pages"] = pages
                if len(pages) == 1:
                    entry["page"] = pages[0]
            if field_ids:
                entry["fieldIds"] = field_ids
            if table_ids:
                entry["tableIds"] = table_ids
            if columns:
                entry["columns"] = columns
            if confidences:
                entry["confidenceAggregate"] = sum(confidences) / len(confidences)
            finalized[identifier] = entry
        return finalized

    def _normalize_absence_details(self, raw_value: str) -> dict:
        """Attempt to parse composite absence detail text into structured fields."""

        details: Dict[str, Optional[str]] = {
            "rawText": raw_value.strip(),
            "departureDate": None,
            "returnDate": None,
            "reason": None,
            "admissionDate": None,
            "dischargeDate": None,
        }

        tokens = [segment.strip() for segment in re.split(r"[\n;]+", raw_value) if segment.strip()]
        patterns: Tuple[Tuple[str, str], ...] = (
            ("departureDate", "departure"),
            ("returnDate", "return"),
            ("reason", "reason"),
            ("admissionDate", "admission"),
            ("dischargeDate", "discharge"),
        )

        for token in tokens:
            lower = token.lower()
            for key, needle in patterns:
                if needle in lower and details[key] is None:
                    value = token.split(":", 1)[-1].strip() if ":" in token else token.replace(needle, "", 1).strip()
                    details[key] = value or None
                    break

        return {k: v for k, v in details.items() if v is not None or k == "rawText"}

    def _extract_line_items(
        self,
        table: "TableExtraction",
        page_number: int,
    ) -> Optional[Dict[str, Any]]:
        """Derive canonical UB-04 line items structured as canonical value tables."""

        header_rows = {cell.row for cell in table.cells if cell.is_header}
        if not header_rows and table.num_rows:
            header_rows = {0}

        column_headers: Dict[int, str] = {}
        for cell in table.cells:
            if cell.row in header_rows:
                header_value = cell.content.strip()
                if not header_value:
                    continue
                column_headers[cell.column] = header_value

        normalized_headers: Dict[int, str] = {}
        for column, header_value in column_headers.items():
            key = self._normalize_line_item_header(header_value)
            if key:
                normalized_headers[column] = key

        if not normalized_headers:
            return None

        data_rows = sorted({row for row in range(table.num_rows)} - header_rows)
        if not data_rows:
            return None

        items: list[dict[str, dict]] = []
        all_confidences: list[float] = []
        for row_index in data_rows:
            row_cells = table.get_row(row_index)
            if not row_cells:
                continue
            item_values: Dict[str, dict] = {}
            row_confidences: list[float] = []
            for cell in row_cells:
                if cell.confidence is not None:
                    row_confidences.append(cell.confidence.value)
                header_key = normalized_headers.get(cell.column)
                if header_key:
                    value_text = cell.content.strip()
                    if not value_text:
                        continue
                    entry = item_values.setdefault(
                        header_key,
                        {
                            "value": None,
                            "confidence": None,
                            "sources": [],
                        },
                    )
                    cell_confidence = cell.confidence.value if cell.confidence else None
                    if entry["confidence"] is None or (cell_confidence or 0.0) >= (entry["confidence"] or 0.0):
                        entry["value"] = value_text
                        entry["confidence"] = cell_confidence
                    source = {
                        "page": page_number,
                        "tableId": str(table.id),
                        "column": cell.column,
                        "row": row_index,
                    }
                    if source not in entry["sources"]:
                        entry["sources"].append(source)
            if not any(item_values.get(key) for key in ("description", "totalCharge", "revenueCode", "procedureCode")):
                continue
            if row_confidences:
                confidence_value = mean(row_confidences)
                all_confidences.append(confidence_value)
                for value_entry in item_values.values():
                    if value_entry.get("confidence") is None:
                        value_entry["confidence"] = confidence_value
            else:
                table_confidence = table.confidence.value if table.confidence else None
                if table_confidence is not None:
                    for value_entry in item_values.values():
                        if value_entry.get("confidence") is None:
                            value_entry["confidence"] = table_confidence
            for value_entry in item_values.values():
                if value_entry.get("value") is None:
                    value_entry["confidence"] = value_entry.get("confidence")
            items.append(item_values)

        if not items:
            return None

        headers_payload = [
            {
                "columnIndex": column,
                "label": column_headers[column],
                "key": normalized_headers.get(column),
            }
            for column in sorted(normalized_headers.keys())
        ]

        table_confidence_value = table.confidence.value if table.confidence else None
        overall_confidence = (
            mean(all_confidences)
            if all_confidences
            else table_confidence_value
        )

        return {
            "tableId": str(table.id),
            "title": table.title,
            "confidence": overall_confidence,
            "headers": headers_payload,
            "items": items,
            "sources": [
                {
                    "page": page_number,
                    "tableId": str(table.id),
                }
            ],
        }

    @staticmethod
    def _normalize_line_item_header(label: str) -> Optional[str]:
        sanitized_label = CanonicalMapper._sanitize(label)

        # Prefer exact matches first
        for alias, key in LINE_ITEM_HEADER_ALIASES.items():
            token = CanonicalMapper._sanitize(alias)
            if sanitized_label == token:
                return key

        # Fallback to substring matches for sufficiently descriptive tokens
        sorted_aliases = sorted(
            LINE_ITEM_HEADER_ALIASES.items(),
            key=lambda item: len(CanonicalMapper._sanitize(item[0])),
            reverse=True,
        )
        for alias, key in sorted_aliases:
            token = CanonicalMapper._sanitize(alias)
            if len(token) < 3:
                continue
            if token in sanitized_label:
                return key
        return None


class _IdentityAccumulator:
    """Accumulates duplicate identity block fields into structured blocks."""

    def __init__(self) -> None:
        self._blocks: list[dict] = []
        self._sequence = 1

    def add(
        self,
        *,
        canonical_field: CanonicalField,
        value: Optional[str],
        page_number: int,
        field_id: str,
    ) -> None:
        attribute = IDENTITY_ATTRIBUTE_MAP.get(canonical_field.identifier)
        block_type = IDENTITY_BLOCK_TYPE_MAP.get(canonical_field.identifier, "identity")
        if attribute is None:
            return
        block = self._locate_block(block_type, page_number)
        block[attribute] = value
        block["present_fields"].add(canonical_field.identifier)
        block["source_field_ids"].add(field_id)

    def _locate_block(self, block_type: str, page_number: int) -> dict:
        for block in self._blocks:
            if block["block_type"] == block_type and block["source_page"] == page_number:
                return block
        new_block = {
            "block_type": block_type,
            "sequence": self._sequence,
            "policy_number": None,
            "policyholder_name": None,
            "policyholder_address": None,
            "provider_name": None,
            "provider_address": None,
            "patient_name": None,
            "patient_address": None,
            "birth_date": None,
            "type_of_bill": None,
            "fed_tax_no": None,
            "statement_period": None,
            "source_page": page_number,
            "present_fields": set(),
            "source_field_ids": set(),
        }
        self._sequence += 1
        self._blocks.append(new_block)
        return new_block

    def serialize(self) -> list[dict]:
        serialized: list[dict] = []
        for block in self._blocks:
            identity = IdentityBlock(
                block_type=block["block_type"],
                sequence=block["sequence"],
                present_fields=tuple(sorted(block["present_fields"])),
                policy_number=block["policy_number"],
                policyholder_name=block["policyholder_name"],
                policyholder_address=block["policyholder_address"],
                provider_name=block["provider_name"],
                provider_address=block["provider_address"],
                patient_name=block["patient_name"],
                patient_address=block["patient_address"],
                birth_date=block["birth_date"],
                type_of_bill=block["type_of_bill"],
                fed_tax_no=block["fed_tax_no"],
                statement_period=block["statement_period"],
                source_page=block["source_page"],
                source_field_ids=tuple(sorted(block["source_field_ids"])),
            )
            serialized.append(identity.to_dict())
        serialized.sort(key=lambda item: item["sequence"])
        return serialized


class _InvoiceLineItemAccumulator:
    """Coalesce general invoice fields into structured line item entries."""

    def __init__(self) -> None:
        self._items_by_page: dict[int, list[dict[str, dict]]] = {}

    def add(
        self,
        *,
        canonical_field: CanonicalField,
        raw_value: Optional[str],
        confidence: float,
        page_number: int,
        field_name: str,
        field_id: Optional[str],
    ) -> None:
        attribute = canonical_field.line_item_attribute
        if attribute is None:
            return
        if raw_value is None or not str(raw_value).strip():
            return

        page_items = self._items_by_page.setdefault(page_number, [])
        index = self._infer_index(field_name)

        if index is None:
            if attribute == "description" or not page_items:
                page_items.append({})
                index = len(page_items)
            else:
                index = len(page_items)
        else:
            while len(page_items) < index:
                page_items.append({})

        item = page_items[index - 1]
        entry = item.setdefault(
            attribute,
            {
                "value": None,
                "confidence": None,
                "sources": [],
            },
        )

        if entry.get("confidence") is None or confidence >= (entry.get("confidence") or 0):
            entry["value"] = raw_value
            entry["confidence"] = confidence

        source: dict[str, object] = {"page": page_number}
        if field_id:
            source["fieldId"] = field_id

        existing_sources = entry.setdefault("sources", [])
        if source not in existing_sources:
            existing_sources.append(source)

    def serialize(self) -> list[dict[str, dict]]:
        ordered_items: list[dict[str, dict]] = []
        for page_number in sorted(self._items_by_page):
            ordered_items.extend(self._items_by_page[page_number])
        return ordered_items

    @staticmethod
    def _infer_index(field_name: str) -> Optional[int]:
        tokens = re.findall(r"(\d+)", field_name)
        if not tokens:
            return None
        try:
            return max(int(token) for token in tokens)
        except ValueError:  # pragma: no cover - defensive
            return None


__all__ = [
    "CanonicalMapper",
    "CanonicalValue",
    "CanonicalSource",
]
