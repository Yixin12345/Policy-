from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from ...models.job import (
  BoundingBox,
  ExtractionJob,
  FieldExtraction,
  TableCell,
  TableExtraction,
)
from ...config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
_client: AzureOpenAI | None = None


def _client_or_raise() -> tuple[AzureOpenAI, str]:
  global _client
  endpoint = settings.ensure_endpoint()
  model = (
    settings.azure_openai_text_model
    or settings.azure_openai_deployment_name
    or settings.azure_openai_vision_model
  )
  if not endpoint or not model:
    raise RuntimeError("Azure OpenAI configuration is incomplete for mapping service")

  if _client is None:
    api_key = settings.azure_openai_api_key
    if api_key:
      _client = AzureOpenAI(
        api_key=api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=endpoint,
      )
    else:
      token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
      )
      _client = AzureOpenAI(
        api_version=settings.azure_openai_api_version,
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
      )

  return _client, model


MAPPING_PROMPT = (
  "You are building canonical data for illumifin claims processing."
  " You are given OCR extraction results (fields and tables) for a multi-page document along with page-level document type hints."
  " Classify the overall content into one or more of: 'facility_invoice', 'cmr_form', 'ub04'."
  " Input JSON includes a pages array where each page has fields with IDs, values, and normalized bounding boxes (x, y, width, height all between 0 and 1 relative to the page)."
  " When populating sources, always reference the provided field IDs (fieldId) or table IDs (tableId) and include the page number."
  " Table metadata includes column headers/keys and cell-level bounding boxes; include the column name when pointing to table sources."
  " Then produce a JSON object matching this schema exactly: {\n"
  "  \"generatedAt\": ISO8601 timestamp,\n"
  "  \"documentTypes\": [string],\n"
  "  \"facilityInvoice\": { optional, object with keys \"general\" (dict of canonical field name -> value object) and \"lineItems\" (list of dict canonicalName->value object) },\n"
  "  \"cmrForm\": { optional, similar structure with sections },\n"
  "  \"ub04\": { optional, provider fields },\n"
  "  \"notes\": [string]\n"
  " }.\n"
  "Each canonical value object must be of form {\"value\": string or null, \"confidence\": number 0-1, \"sources\": [ {\"page\": int optional, \"fieldId\": string optional, \"tableId\": string optional, \"column\": string optional } ] }."
  " Confidence is your mapping confidence (not OCR confidence)."
  " Populate as many facility invoice fields as possible: policyNumber, policyholderName, policyholderAddress, providerName, providerAddress, invoiceNumber, invoiceDate, taxId, totalAmount, balanceDue, credits."
  " For lineItems include description, startDate, endDate, unitType, quantity, amount, balance, totalDue, credits."
  " For CMR include policyNumber, policyholderName, policyholderAddress, providerName, providerAddress, serviceFrom, serviceThrough, careLevelSelection, absenceIndicator (yes/no) plus absenceDetails (departureDate, returnDate, reason, admissionDate, dischargeDate), insuranceIndicator and insuranceSelections (medicare, medicaid, other), signaturePresent (yes/blank) and signatureDate."
  " For UB04 include providerName, providerAddress."
  " Always provide an empty object for a section if it applies but data is missing."
  " If no content applies, set documentTypes to ['other'] and return empty sections."
  " Do not invent data. Leave value as null when evidence is absent."
  " Provide reasoning notes in the notes array when confidence is low."
)


def _serialize_bbox(bbox: Optional[BoundingBox]) -> Optional[Dict[str, Any]]:
  if not bbox:
    return None
  return {
    "x": float(bbox.x),
    "y": float(bbox.y),
    "width": float(bbox.width),
    "height": float(bbox.height),
    "normalized": True,
  }


def _serialize_field(field: FieldExtraction) -> Dict[str, Any]:
  payload: Dict[str, Any] = {
    "id": field.id,
    "page": field.page,
    "name": field.name,
    "value": field.value,
    "confidence": field.confidence,
    "bbox": _serialize_bbox(field.bbox),
    "sourceType": field.source_type,
    "revised": field.revised,
  }
  if field.original_value is not None:
    payload["originalValue"] = field.original_value
  return payload


def _serialize_cell(cell: TableCell) -> Dict[str, Any]:
  return {
    "value": cell.value,
    "confidence": cell.confidence,
    "bbox": _serialize_bbox(cell.bbox),
  }


def _serialize_table(table: TableExtraction) -> Dict[str, Any]:
  return {
    "id": table.id,
    "page": table.page,
    "caption": table.caption,
    "confidence": table.confidence,
    "bbox": _serialize_bbox(table.bbox),
    "normalized": table.normalized,
    "columns": [
      {
        "key": column.key,
        "header": column.header,
        "type": column.type,
        "confidence": column.confidence,
      }
      for column in table.columns
    ],
    "rows": [
      [_serialize_cell(cell) for cell in row]
      for row in table.rows
    ],
    "tableGroupId": table.table_group_id,
    "continuationOf": table.continuation_of,
    "inferredHeaders": table.inferred_headers,
    "rowStartIndex": table.row_start_index,
  }


def build_mapping_payload(job: ExtractionJob) -> Dict[str, Any]:
  aggregated = job.aggregated or {}
  page_hints = [
    {
      "page": page.page_number,
      "label": page.document_type_hint,
      "confidence": page.document_type_confidence,
    }
    for page in job.pages
    if page.document_type_hint or page.document_type_confidence is not None
  ]

  pages_payload: List[Dict[str, Any]] = []
  for page in job.pages:
    page_payload: Dict[str, Any] = {
      "pageNumber": page.page_number,
      "status": page.status,
      "documentTypeHint": page.document_type_hint,
      "documentTypeConfidence": page.document_type_confidence,
      "rotationApplied": page.rotation_applied,
      "fields": [_serialize_field(field) for field in page.fields],
      "tables": [_serialize_table(table) for table in page.tables],
    }
    if page.error_message:
      page_payload["errorMessage"] = page.error_message
    if page.image_path:
      page_payload["imagePath"] = str(page.image_path)
    if page.image_mime:
      page_payload["imageMime"] = page.image_mime
    pages_payload.append(page_payload)

  return {
    "jobId": job.status.job_id,
    "documentType": job.document_type,
    "originalFilename": job.metadata.get("originalFilename"),
    "pageClassifications": page_hints,
    "aggregated": aggregated,
    "mergedTables": job.metadata.get("mergedTables"),
    "tableGroups": job.metadata.get("tableGroups"),
    "pages": pages_payload,
  }


def generate_canonical_bundle(job: ExtractionJob) -> Tuple[Dict[str, Any], Dict[str, Any]]:
  payload = build_mapping_payload(job)
  client, model = _client_or_raise()

  messages = [
    {"role": "system", "content": MAPPING_PROMPT},
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": (
            "Using the following JSON data, produce the canonical response."
            " Respond with JSON only."
          ),
        },
        {
          "type": "text",
          "text": json.dumps(payload, ensure_ascii=False),
        },
      ],
    },
  ]

  response = client.chat.completions.create(
    model=model,
    messages=messages,
    response_format={"type": "json_object"},
    # max_completion_tokens=8000,
  )

  raw_content = response.choices[0].message.content if response.choices else ""
  if not raw_content:
    raise RuntimeError("Mapping model returned empty response")

  try:
    canonical = json.loads(raw_content)
  except json.JSONDecodeError as exc:  # pragma: no cover - defensive
    logger.warning("Failed to parse canonical mapping JSON: %s", raw_content)
    raise RuntimeError("Mapping model returned invalid JSON") from exc

  canonical.setdefault("generatedAt", datetime.now(timezone.utc).isoformat())
  canonical.setdefault("documentTypes", [])
  canonical.setdefault("notes", [])

  trace = {
    "prompt": {
      "system": MAPPING_PROMPT,
      "payload": payload,
    },
    "response": raw_content,
    "model": model,
  }
  return canonical, trace
