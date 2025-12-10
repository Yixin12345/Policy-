"""Azure OpenAI mapping client enriched with Azure AI Search for policy conversion."""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from backend.config import get_settings
from backend.domain.entities.job import Job
from backend.domain.services.canonical_mapper import CanonicalMapper
from backend.domain.value_objects.canonical_field import CanonicalFieldIndex

from .azure_search_client import AzureSearchClient
from .canonical_transformer import CanonicalTransformer, CanonicalPayload
from .prompt_builder import CanonicalPromptBuilder, PromptBundle

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MappingResult:
    """Return value for mapping operations."""

    canonical: Dict[str, Any]
    trace: Dict[str, Any]


class AzureMappingClient:
    """Adapter responsible for canonical document generation via Azure OpenAI + Azure Search."""

    def __init__(
        self,
        *,
        client: Optional[AzureOpenAI] = None,
        transformer: Optional[CanonicalTransformer] = None,
        prompt_builder: Optional[CanonicalPromptBuilder] = None,
        mapper: Optional[CanonicalMapper] = None,
        search_client: Optional[AzureSearchClient] = None,
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
        self._search_client = search_client or AzureSearchClient()

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

        search_hits = self._search_client.search_fields(
            fields=CanonicalFieldIndex.ordered(),
            job_id=job.job_id,
            top_k=3,
        )

        deterministic_bundle = self._canonical_mapper.map_document(
            job.pages,
            search_hits=search_hits,
        )

        prompt_bundle = self._prompt_builder.build(
            search_snippets=search_hits,
        )

        guidance_text = self._compose_guidance_text(prompt_bundle)

        messages = [
            {"role": "system", "content": prompt_bundle.system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": guidance_text},
                    {"type": "text", "text": prompt_bundle.search_context},
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
        )

        canonical, raw_content = self._coerce_json_payload(response)

        canonical = merge_canonical_bundles(deterministic_bundle, canonical)
        canonical["generatedAt"] = canonical.get("generatedAt") or datetime.now(timezone.utc).isoformat()
        canonical["documentTypes"] = ["policy_conversion"]
        canonical["documentCategories"] = ["policy_conversion"]
        canonical.setdefault("reasoningNotes", [])
        canonical = _normalize_policy_conversion(canonical)

        trace = {
            "prompt": {
                "system": prompt_bundle.system_prompt,
                "instructions": prompt_bundle.instructions,
                "outputSchema": prompt_bundle.output_schema,
                "schema": prompt_bundle.schema_summary,
                "payload": payload.payload,
            },
            "search": search_hits,
            "deterministic": deterministic_bundle,
            "response": raw_content,
            "model": self._model,
        }

        return MappingResult(canonical=canonical, trace=trace)

    def _compose_guidance_text(self, bundle: PromptBundle) -> str:
        parts = [
            bundle.instructions,
            "",
            "Schema summary:",
            bundle.schema_summary,
            "",
            "Output schema:",
            bundle.output_schema,
        ]
        return "\n".join(parts)

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
            canonical = json.loads(json.dumps(parsed))
            return canonical, json.dumps(canonical)

        content = getattr(message, "content", "")
        if not content:
            raise RuntimeError("Mapping model returned empty content")
        try:
            canonical = json.loads(content)
        except Exception as exc:
            logger.error("Failed to parse canonical payload: %s", exc)
            raise
        return canonical, content


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------
def merge_canonical_bundles(deterministic: Dict[str, Any], llm: Dict[str, Any]) -> Dict[str, Any]:
    """Merge LLM bundle into deterministic skeleton, preferring deterministic when present."""

    merged = deepcopy(deterministic) if isinstance(deterministic, dict) else {}
    if not isinstance(llm, dict):
        return merged

    merged["schemaVersion"] = llm.get("schemaVersion") or merged.get("schemaVersion")
    merged["generatedAt"] = llm.get("generatedAt") or merged.get("generatedAt")
    merged["documentTypes"] = llm.get("documentTypes") or merged.get("documentTypes") or ["policy_conversion"]
    merged["documentCategories"] = llm.get("documentCategories") or merged.get("documentCategories") or ["policy_conversion"]

    policy_conv = merged.get("policyConversion", {}) or {}
    llm_policy = llm.get("policyConversion") or {}
    for label, value in llm_policy.items():
        existing = policy_conv.get(label)
        if _has_value(existing):
            # keep deterministic/search seed unless LLM supplies better confidence
            if isinstance(existing, dict) and isinstance(value, dict):
                if (existing.get("confidence") or 0) < (value.get("confidence") or 0):
                    policy_conv[label] = value
            continue
        policy_conv[label] = value
    merged["policyConversion"] = policy_conv
    merged["sourceMap"] = llm.get("sourceMap") or merged.get("sourceMap") or {}
    if llm.get("reasoningNotes"):
        merged["reasoningNotes"] = llm.get("reasoningNotes")
    return merged


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return bool(value.get("value") not in (None, "", []))
    return True


def _normalize_policy_conversion(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure only policyConversion is present and all 60 fields exist."""

    allowed_keys = {
        "policyConversion",
        "schemaVersion",
        "generatedAt",
        "reasoningNotes",
        "notes",
        "documentCategories",
        "documentTypes",
        "sourceMap",
        "trace",
    }

    # Drop legacy sections
    for legacy_key in ("facilityInvoice", "invoice", "cmr", "cmrForm", "ub04", "ub04LineItems", "invoiceLineItems"):
        bundle.pop(legacy_key, None)

    # Build complete policyConversion block
    existing = bundle.get("policyConversion")
    normalized: Dict[str, Any] = {}
    if isinstance(existing, dict):
        normalized.update(existing)
    for field in CanonicalFieldIndex.ordered():
        if field.label not in normalized or normalized[field.label] is None:
            normalized[field.label] = {"value": None, "confidence": None, "sources": []}
    bundle["policyConversion"] = normalized

    # Clean keys
    for key in list(bundle.keys()):
        if key not in allowed_keys:
            bundle.pop(key, None)

    bundle["documentTypes"] = ["policy_conversion"]
    bundle["documentCategories"] = ["policy_conversion"]
    return bundle
