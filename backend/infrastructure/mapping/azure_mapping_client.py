"""Azure OpenAI based mapping client for canonical document generation."""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from backend.config import get_settings
from backend.domain.entities.job import Job
from backend.domain.services.canonical_mapper import CanonicalMapper

from .canonical_transformer import CanonicalTransformer, CanonicalPayload
from .prompt_builder import CanonicalPromptBuilder, PromptBundle

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MappingResult:
    """Return value for mapping operations."""

    canonical: Dict[str, Any]
    trace: Dict[str, Any]


class AzureMappingClient:
    """Adapter responsible for canonical document generation via Azure OpenAI."""

    _MAPPER_CATEGORY_ALIASES: Dict[str, str] = {
        "facility_invoice": "INVOICE",
        "facility-invoice": "INVOICE",
        "invoice": "INVOICE",
        "general_invoice": "INVOICE",
        "cmr_form": "CMR",
        "cmr": "CMR",
        "continued_monthly_residence": "CMR",
        "ub04": "UB04",
        "ub-04": "UB04",
        "ub 04": "UB04",
    }

    def __init__(
        self,
        *,
        client: Optional[OpenAI] = None,
        transformer: Optional[CanonicalTransformer] = None,
        prompt_builder: Optional[CanonicalPromptBuilder] = None,
        mapper: Optional[CanonicalMapper] = None,
    ) -> None:
        settings = get_settings()
        api_key = settings.azure_openai_api_key
        endpoint = settings.ensure_endpoint()
        model = (
            settings.azure_openai_text_model
            or settings.azure_openai_deployment_name
            or settings.azure_openai_vision_model
        )

        if not endpoint or not model:
            raise RuntimeError("Azure OpenAI configuration is incomplete for mapping client")

        if client is not None:
            self._client = client
        else:
            if api_key:
                self._client = AzureOpenAI(
                    api_key=api_key,
                    api_version=settings.azure_openai_api_version,
                    azure_endpoint=endpoint,
                )
            else:
                token_provider = get_bearer_token_provider(
                    DefaultAzureCredential(),
                    "https://cognitiveservices.azure.com/.default",
                )
                self._client = AzureOpenAI(
                    api_version=settings.azure_openai_api_version,
                    azure_endpoint=endpoint,
                    azure_ad_token_provider=token_provider,
                )

        self._model = model
        self._transformer = transformer or CanonicalTransformer()
        self._prompt_builder = prompt_builder or CanonicalPromptBuilder()
        self._canonical_mapper = mapper or CanonicalMapper()

    def generate(
        self,
        job: Job,
        *,
        aggregated: Optional[Dict[str, Any]] = None,
        table_groups: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MappingResult:
        payload: CanonicalPayload = self._transformer.build_payload(
            job,
            aggregated=aggregated,
            table_groups=table_groups,
            metadata=metadata,
        )

        document_categories = list(self._extract_document_categories(payload.payload))
        document_categories.extend(self._extract_document_categories(metadata))

        page_categories = self._extract_page_categories(payload.payload)
        meta_page_categories = self._extract_page_categories(metadata)
        page_categories.update(meta_page_categories)

        unique_document_categories = list(dict.fromkeys(document_categories))

        mapper_document_categories = self._mapper_categories(unique_document_categories)
        mapper_page_categories = self._mapper_page_categories(page_categories)

        deterministic_bundle = self._canonical_mapper.map_document(
            job.pages,
            document_categories=mapper_document_categories or None,
            page_categories=mapper_page_categories or None,
        )

        prompt_bundle = self._prompt_builder.build(
            document_categories=unique_document_categories,
            page_categories=page_categories,
        )

        guidance_text = self._compose_guidance_text(prompt_bundle)

        messages = [
            {"role": "system", "content": prompt_bundle.system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": guidance_text},
                    {
                        "type": "text",
                        "text": "Deterministic canonical skeleton (do not overwrite high-confidence values):",
                    },
                    {"type": "text", "text": json.dumps(deterministic_bundle, ensure_ascii=False)},
                    {"type": "text", "text": "Extraction JSON:"},
                    {"type": "text", "text": json.dumps(payload.payload, ensure_ascii=False)},
                ],
            },
        ]

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"},
            # max_completion_tokens=8000,
        )

        canonical, raw_content = self._coerce_json_payload(response)

        canonical = merge_canonical_bundles(deterministic_bundle, canonical)
        canonical.setdefault("generatedAt", datetime.now(timezone.utc).isoformat())
        canonical.setdefault("documentTypes", [])
        canonical.setdefault("reasoningNotes", [])

        trace = {
            "prompt": {
                "system": prompt_bundle.system_prompt,
                "instructions": prompt_bundle.instructions,
                "outputSchema": prompt_bundle.output_schema,
                "schema": prompt_bundle.schema_summary,
                "payload": payload.payload,
                "documentCategories": unique_document_categories,
                "pageCategories": page_categories,
            },
            "deterministic": deterministic_bundle,
            "response": raw_content,
            "model": self._model,
        }

        return MappingResult(canonical=canonical, trace=trace)

    def _coerce_json_payload(self, response: Any) -> tuple[dict, str]:
        """Extract JSON payload from chat completion, accommodating SDK variants."""

        if not response or not getattr(response, "choices", None):
            raise RuntimeError("Mapping model returned empty response")

        choice = response.choices[0]
        message = getattr(choice, "message", None)
        if message is None:
            raise RuntimeError("Mapping model returned empty response")

        logger.debug("Canonical mapping message payload: %s", getattr(message, "__dict__", message))

        parsed = getattr(message, "parsed", None)
        if parsed:
            # Ensure we return a plain dict/json string (message.parsed can be pydantic object)
            canonical = json.loads(json.dumps(parsed))
            return canonical, json.dumps(canonical)

        content = getattr(message, "content", "")
        raw_content = self._stringify_content(content)
        if not raw_content:
            logger.warning("Canonical mapping returned empty content: %s", content)
            raise RuntimeError("Mapping model returned empty response")

        try:
            canonical = json.loads(raw_content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            logger.warning("Failed to parse canonical mapping JSON: %s", raw_content)
            raise RuntimeError("Mapping model returned invalid JSON") from exc

        return canonical, raw_content

    @staticmethod
    def _stringify_content(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                text = None
                if isinstance(item, dict):
                    text = item.get("text")
                else:
                    text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
            return "".join(parts).strip()
        return str(content).strip()

    def _compose_guidance_text(self, prompt_bundle: PromptBundle) -> str:
        return (
            prompt_bundle.instructions
            + "\n\nOutput requirements:\n"
            + prompt_bundle.output_schema
            + "\n\nCanonical schema overview:\n"
            + prompt_bundle.schema_summary
            + "\n\nFill in the canonical bundle using the provided skeleton and extraction payload."
        )

    def _extract_document_categories(
        self, metadata: Optional[Dict[str, Any]]
    ) -> Sequence[str]:
        if not metadata:
            return []
        categories: List[str] = []
        raw_categories = metadata.get("documentCategories")
        if isinstance(raw_categories, list):
            categories.extend(str(category) for category in raw_categories if category)
        raw_primary = metadata.get("documentType")
        if raw_primary and isinstance(raw_primary, str):
            categories.append(raw_primary)
        return categories

    def _extract_page_categories(
        self, metadata: Optional[Dict[str, Any]]
    ) -> Dict[int, str]:
        if not metadata:
            return {}
        raw = metadata.get("pageCategories")
        if not isinstance(raw, dict):
            return {}
        page_categories: Dict[int, str] = {}
        for key, value in raw.items():
            if value is None:
                continue
            try:
                page_key = int(key)
            except (TypeError, ValueError):
                continue
            page_categories[page_key] = str(value)
        return page_categories

    def _mapper_categories(self, categories: Sequence[str]) -> List[str]:
        normalized: List[str] = []
        seen: set[str] = set()
        for category in categories:
            token = self._normalize_category_token(category)
            if token is None or token in seen:
                continue
            seen.add(token)
            normalized.append(token)
        return normalized

    def _mapper_page_categories(self, page_categories: Dict[int, str]) -> Dict[int, List[str]]:
        normalized: Dict[int, List[str]] = {}
        for page, category in page_categories.items():
            tokens = self._mapper_categories([category])
            if tokens:
                normalized[page] = tokens
        return normalized

    def _normalize_category_token(self, category: str) -> Optional[str]:
        normalized = (category or "").strip().lower()
        if not normalized:
            return None
        alias = self._MAPPER_CATEGORY_ALIASES.get(normalized)
        if alias:
            return alias
        return normalized.upper()


def merge_canonical_bundles(
    deterministic: Dict[str, Any] | None,
    llm: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Merge deterministic canonical bundle with LLM output safely."""

    base = deepcopy(deterministic or {})
    llm = llm or {}

    if "schemaVersion" not in base and llm.get("schemaVersion"):
        base["schemaVersion"] = llm["schemaVersion"]
    if "generatedAt" not in base and llm.get("generatedAt"):
        base["generatedAt"] = llm["generatedAt"]

    base.setdefault("documentCategories", list(base.get("documentCategories", [])))
    base.setdefault("identityBlocks", list(base.get("identityBlocks", [])))
    base.setdefault("reasoningNotes", list(base.get("reasoningNotes", [])))
    base.setdefault("sourceMap", dict(base.get("sourceMap", {})))
    base.setdefault("invoiceLineItems", list(base.get("invoiceLineItems", [])))
    base.setdefault("ub04LineItems", list(base.get("ub04LineItems", [])))

    llm_doc_categories = _as_list(llm.get("documentCategories") or llm.get("document_categories"))
    if llm_doc_categories:
        base["documentCategories"] = _dedupe_preserve_order(
            list(base.get("documentCategories", []))
            + [str(item) for item in llm_doc_categories if item]
        )

    llm_doc_types = _as_list(llm.get("documentTypes") or llm.get("document_types"))
    base["documentTypes"] = _dedupe_preserve_order(
        list(base.get("documentTypes", []))
        + [str(item) for item in llm_doc_types if item]
    )

    llm_notes = _as_list(llm.get("reasoningNotes") or llm.get("notes"))
    if llm_notes:
        base["reasoningNotes"] = _dedupe_preserve_order(
            list(base.get("reasoningNotes", []))
            + [str(item) for item in llm_notes if item]
        )

    for group_key in ("invoice", "cmr", "ub04"):
        deterministic_group = base.get(group_key)
        llm_group = llm.get(group_key)
        merged_group = _merge_canonical_group(deterministic_group, llm_group)
        if merged_group is not None:
            base[group_key] = merged_group

    deterministic_line_items = _normalize_line_items(base.get("invoiceLineItems"))
    base["invoiceLineItems"] = deterministic_line_items

    deterministic_ub04_line_items = _normalize_ub04_line_items(base.get("ub04LineItems"))
    base["ub04LineItems"] = deterministic_ub04_line_items

    llm_line_items = _extract_llm_line_items(llm)
    normalized_llm_line_items = _normalize_line_items(llm_line_items)
    if normalized_llm_line_items:
        base["invoiceLineItems"] = normalized_llm_line_items

    llm_ub04_line_items = _normalize_ub04_line_items(llm.get("ub04LineItems"))
    if not base.get("ub04LineItems") and llm_ub04_line_items:
        base["ub04LineItems"] = llm_ub04_line_items

    if not base.get("identityBlocks") and isinstance(llm.get("identityBlocks"), list):
        base["identityBlocks"] = llm["identityBlocks"]

    base["sourceMap"] = _merge_source_map(base.get("sourceMap"), llm.get("sourceMap"))

    return base


def _merge_canonical_group(
    deterministic_group: Optional[Dict[str, Any]],
    llm_group: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if deterministic_group is None:
        if isinstance(llm_group, dict):
            return {
                label: _normalize_value_entry(entry)
                for label, entry in llm_group.items()
            }
        return deterministic_group

    merged_group: Dict[str, Any] = deterministic_group.__class__()
    llm_group = llm_group if isinstance(llm_group, dict) else {}

    for label, deterministic_entry in deterministic_group.items():
        normalized_det = _normalize_value_entry(deterministic_entry)
        llm_entry = _normalize_value_entry(llm_group.get(label)) if label in llm_group else None
        merged_group[label] = _merge_value_entry(normalized_det, llm_entry)

    return merged_group


def _normalize_value_entry(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        return {"value": entry, "confidence": None, "sources": []}
    value = entry.get("value") if "value" in entry else entry.get("Value")
    confidence = entry.get("confidence") if "confidence" in entry else entry.get("Confidence")
    sources = entry.get("sources") if "sources" in entry else entry.get("Sources")
    return {
        "value": value,
        "confidence": confidence,
        "sources": list(sources or []),
    }


def _merge_value_entry(
    deterministic_entry: Dict[str, Any],
    llm_entry: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    merged = {
        "value": deterministic_entry.get("value"),
        "confidence": deterministic_entry.get("confidence"),
        "sources": list(deterministic_entry.get("sources") or []),
    }

    if _has_value(merged["value"]):
        llm_sources = (llm_entry or {}).get("sources") if llm_entry else []
        if llm_sources:
            merged["sources"] = _merge_sources(merged["sources"], llm_sources)
        if merged.get("confidence") is None and llm_entry and llm_entry.get("confidence") is not None:
            merged["confidence"] = llm_entry.get("confidence")
        return merged

    if llm_entry is None:
        merged["value"] = None
        merged["confidence"] = None
        merged["sources"] = []
        return merged

    merged["value"] = llm_entry.get("value")
    merged["confidence"] = llm_entry.get("confidence")
    merged["sources"] = list(llm_entry.get("sources") or [])
    return merged


def _normalize_line_items(line_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(line_items, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in line_items:
        if not isinstance(item, dict):
            continue
        normalized_item: Dict[str, Any] = {}
        for key, entry in item.items():
            normalized_item[str(key)] = _normalize_value_entry(entry)
        normalized.append(normalized_item)
    return normalized


def _normalize_ub04_line_items(tables: Any) -> List[Dict[str, Any]]:
    if not isinstance(tables, list):
        return []
    normalized_tables: List[Dict[str, Any]] = []
    for table in tables:
        if not isinstance(table, dict):
            continue

        table_id = table.get("tableId") or table.get("table_id") or table.get("id")
        title = table.get("title") or table.get("name")
        confidence = table.get("confidence")
        sources = table.get("sources") if isinstance(table.get("sources"), list) else None

        raw_headers = table.get("headers") or table.get("columns")
        headers: List[Dict[str, Any]] = []
        if isinstance(raw_headers, list):
            for index, header in enumerate(raw_headers):
                if isinstance(header, dict):
                    headers.append(
                        {
                            "columnIndex": header.get("columnIndex") if isinstance(header.get("columnIndex"), int) else index,
                            "label": header.get("label") or header.get("header") or header.get("name"),
                            "key": header.get("key") or header.get("id"),
                        }
                    )
                elif isinstance(header, str):
                    headers.append(
                        {
                            "columnIndex": index,
                            "label": header,
                            "key": None,
                        }
                    )

        normalized_items: List[Dict[str, Any]] = []
        raw_items = table.get("items") or table.get("rows")
        if isinstance(raw_items, list):
            for row in raw_items:
                if isinstance(row, dict):
                    normalized_row: Dict[str, Any] = {}
                    fields_source = row.get("fields") if isinstance(row.get("fields"), dict) else None
                    cells_source = row.get("cells") if isinstance(row.get("cells"), list) else None
                    values_source = row.get("values") if isinstance(row.get("values"), dict) else None

                    if fields_source is not None:
                        for key, value in fields_source.items():
                            normalized_row[str(key)] = _normalize_value_entry(value)
                    elif values_source is not None:
                        for key, value in values_source.items():
                            normalized_row[str(key)] = _normalize_value_entry(value)
                    elif cells_source is not None:
                        for index, value in enumerate(cells_source):
                            column_key = None
                            if index < len(headers) and headers[index].get("key"):
                                column_key = headers[index]["key"]
                            elif index < len(headers) and headers[index].get("label"):
                                column_key = headers[index]["label"]
                            elif index < len(headers):
                                column_key = str(index)
                            else:
                                column_key = str(index)
                            normalized_row[str(column_key)] = _normalize_value_entry(value)
                    else:
                        for key, value in row.items():
                            if key in {"fields", "cells", "values", "row"}:
                                continue
                            normalized_row[str(key)] = _normalize_value_entry(value)

                    if normalized_row:
                        normalized_items.append(normalized_row)
                elif isinstance(row, list):
                    normalized_row = {}
                    for index, value in enumerate(row):
                        column_key = None
                        if index < len(headers) and headers[index].get("key"):
                            column_key = headers[index]["key"]
                        elif index < len(headers) and headers[index].get("label"):
                            column_key = headers[index]["label"]
                        else:
                            column_key = str(index)
                        normalized_row[str(column_key)] = _normalize_value_entry(value)
                    if normalized_row:
                        normalized_items.append(normalized_row)

        if not normalized_items:
            continue

        normalized_table = {
            "tableId": str(table_id) if table_id is not None else None,
            "title": title,
            "confidence": confidence,
            "headers": headers,
            "items": normalized_items,
        }
        if sources:
            normalized_table["sources"] = sources

        normalized_tables.append(normalized_table)

    return normalized_tables


def _extract_llm_line_items(llm_payload: Dict[str, Any] | None) -> Any:
    if not isinstance(llm_payload, dict):
        return []
    direct = llm_payload.get("invoiceLineItems")
    if isinstance(direct, list):
        return direct
    facility_invoice = llm_payload.get("facilityInvoice")
    if isinstance(facility_invoice, dict):
        line_items = facility_invoice.get("lineItems")
        if isinstance(line_items, list):
            return line_items
    return []


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _merge_sources(existing: List[Dict[str, Any]], new_sources: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    combined = list(existing)
    for source in new_sources:
        if not isinstance(source, dict):
            continue
        if source not in combined:
            combined.append(source)
    return combined


def _merge_source_map(
    deterministic_map: Optional[Dict[str, Any]],
    llm_map: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    base = deepcopy(deterministic_map) if isinstance(deterministic_map, dict) else {}
    if not isinstance(llm_map, dict):
        return base
    for identifier, llm_entry in llm_map.items():
        if not isinstance(llm_entry, dict):
            continue
        existing = base.get(identifier, {})
        merged_entry = dict(existing)
        for key in ("pages", "fieldIds", "tableIds", "columns"):
            values = _dedupe_preserve_order(
                list(existing.get(key, [])) + list(llm_entry.get(key, []))
            )
            if values:
                merged_entry[key] = values
            elif key in merged_entry:
                merged_entry.pop(key)
        if (
            "confidenceAggregate" not in merged_entry
            and isinstance(llm_entry.get("confidenceAggregate"), (int, float))
        ):
            merged_entry["confidenceAggregate"] = float(llm_entry["confidenceAggregate"])
        base[identifier] = merged_entry
    return base


def _dedupe_preserve_order(items: Sequence[Any]) -> List[Any]:
    seen: set[Any] = set()
    deduped: List[Any] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
