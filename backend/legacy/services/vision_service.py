from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from ...models.job import BoundingBox, FieldExtraction, TableCell, TableColumn, TableExtraction
from ...config import get_settings
from ...constants import CONFIDENCE_STEPS
from .pdf_service import image_to_data_url

logger = logging.getLogger(__name__)

settings = get_settings()
AZURE_API_KEY = settings.azure_openai_api_key
AZURE_ENDPOINT = settings.ensure_endpoint()
AZURE_MODEL = (
  settings.azure_openai_vision_model
  or settings.azure_openai_deployment_name
  or settings.azure_openai_text_model
)

_client: Optional[AzureOpenAI] = None


def get_client() -> AzureOpenAI:
  global _client
  if _client is None:
    if not AZURE_ENDPOINT or not AZURE_MODEL:
      raise RuntimeError("Azure OpenAI configuration is incomplete for vision processing")
    if AZURE_API_KEY:
      _client = AzureOpenAI(
        api_key=AZURE_API_KEY,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=AZURE_ENDPOINT,
      )
    else:
      token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
      )
      _client = AzureOpenAI(
        api_version=settings.azure_openai_api_version,
        azure_endpoint=AZURE_ENDPOINT,
        azure_ad_token_provider=token_provider,
      )
  return _client


PROMPT_TEMPLATE = (
  "You are an expert document extraction system. Analyze the document image and return structured JSON only. Your primary goals are:"
  " (1) classify the document page into one of ['facility_invoice','cmr_form','ub04','other'];"
  " (2) extract field name/value pairs;"
  " (3) extract table structures."
  " You may need to account for sideways table layouts or handwritten notes."
  " Use this exact JSON schema for your response: {\n"
  "  \"documentType\": {\n"
  "    \"label\": string from ['facility_invoice','cmr_form','ub04','other'],\n"
  "    \"confidence\": number between 0 and 1,\n"
  "    \"reasons\": [string]\n"
  "  },\n"
  "  \"fields\": [\n"
  "    {\"id\": string, \"name\": string, \"value\": string, \"confidence\": number between 0 and 1, \"sourceType\": string optional,"
  "     \"bbox\": {\"x\": integer, \"y\": integer, \"width\": integer, \"height\": integer} }\n"
  "  ],\n"
  "  \"tables\": [\n"
  "    {\n"
  "      \"id\": string,\n"
  "      \"caption\": string or null,\n"
  "      \"confidence\": number between 0 and 1,\n"
  "      \"columns\": [{ \"key\": string, \"header\": string, \"type\": string optional, \"confidence\": number optional }],\n"
  "      \"rows\": [[{ \"value\": string, \"confidence\": number optional, \"bbox\": {\"x\": integer, \"y\": integer, \"width\": integer, \"height\": integer} }]]\n"
  "    }\n"
  "  ]\n"
  "}.\n"
  "All bbox coordinates must be provided as integer pixel values relative to the original page image. If a bounding box contains multiple fields, split the block into individual field-value pairs and assign the same bounding box to each field unless more precise boxes are available. Use very small non-zero widths/heights for point-like selections instead of omitting the bbox. Confidence values for fields, tables, and the documentType must be chosen from [0.0, 0.2, 0.4, 0.6, 0.8, 1.0] (0.0 = unreadable, 1.0 = exact match)."
  "Do not add commentary. If nothing is found return {\"documentType\":{\"label\":\"other\",\"confidence\":0.0,\"reasons\":[]},\"fields\":[],\"tables\":[]}."
)


# Use shared confidence steps from constants


def _safe_float(value: Any) -> Optional[float]:
  try:
    if value is None:
      return None
    return float(value)
  except (TypeError, ValueError):
    return None


def _quantize_confidence(value: Optional[float]) -> Optional[float]:
  if value is None:
    return None
  clamped = max(0.0, min(1.0, value))
  step_index = round(clamped / 0.2)
  quantized = round(step_index * 0.2, 1)
  return min(CONFIDENCE_STEPS, key=lambda step: abs(step - quantized))


def _normalize_column_name(value: Any) -> str:
  if value is None:
    return ""
  text = str(value).strip().lower()
  if not text:
    return ""
  return re.sub(r"[^a-z0-9]+", "_", text)


def _parse_bbox(data: Dict[str, Any]) -> Optional[BoundingBox]:
  if not isinstance(data, dict):
    return None
  x = _safe_float(data.get("x"))
  y = _safe_float(data.get("y"))
  width = _safe_float(data.get("width"))
  height = _safe_float(data.get("height"))
  if None in (x, y, width, height):
    return None
  return BoundingBox(x=float(x), y=float(y), width=float(width), height=float(height))


def call_vision_model(image_path: str, page_number: int) -> Dict[str, Any]:
  client = get_client()
  data_url = image_to_data_url(Path(image_path))

  base_messages = [
    {"role": "system", "content": PROMPT_TEMPLATE},
    {
      "role": "user",
      "content": [
        {"type": "text", "text": f"Perform OCR to extract field-value pair data and table data for page {page_number}."},
        {"type": "image_url", "image_url": {"url": data_url}},
      ],
    },
  ]

  attempts = [
    (base_messages, True),
    (base_messages, False),
    (
      [
        base_messages[0],
        {
          "role": "user",
          "content": [
            {
              "type": "text",
              "text": (
                f"Perform OCR to extract field-value pair data and table data for this page {page_number}. If no field-value pair or table data can be extracted, respond with "
                '{"fields":[],"tables":[]} and never leave the response empty.'
              ),
            },
            {"type": "image_url", "image_url": {"url": data_url}},
          ],
        },
      ],
      False,
    ),
  ]

  content: str = ""
  used_json_mode = False
  for messages, force_json in attempts:
    content, used_json_mode = _invoke_model(client, messages, force_json=force_json)
    if content:
      break

  if not content:
    logger.error("Vision model returned empty response after retries for page %s", page_number)
    return {"fields": [], "tables": []}

  payload = _extract_json_payload(content)
  if payload is None:
    logger.warning("Vision response not valid JSON (json_mode=%s): %s", used_json_mode, _truncate_content(content))
    payload = {"fields": [], "tables": []}

  payload.setdefault("documentType", {"label": "other", "confidence": 0.0, "reasons": []})
  payload.setdefault("fields", [])
  payload.setdefault("tables", [])

  _persist_debug_payload(image_path, page_number, content, payload, used_json_mode)
  return payload


def _invoke_model(client: AzureOpenAI, messages: List[Dict[str, Any]], force_json: bool) -> Tuple[str, bool]:
  kwargs: Dict[str, Any] = {
    "model": AZURE_MODEL,
    "messages": messages,
    "max_completion_tokens": 50000,
  }
  if force_json:
    kwargs["response_format"] = {"type": "json_object"}

  response = client.chat.completions.create(**kwargs)
  content = response.choices[0].message.content if response.choices else ""
  return content or "", force_json


def _extract_json_payload(content: str) -> Optional[Dict[str, Any]]:
  text = content.strip()
  if not text:
    return None

  try:
    return json.loads(text)
  except json.JSONDecodeError:
    pass

  fenced = _strip_code_fence(text)
  if fenced and fenced != text:
    try:
      return json.loads(fenced)
    except json.JSONDecodeError:
      pass

  match = re.search(r"\{[\s\S]*\}", text)
  if match:
    snippet = match.group(0)
    try:
      return json.loads(snippet)
    except json.JSONDecodeError:
      return None

  return None


def _strip_code_fence(text: str) -> str:
  if text.startswith("```") and text.endswith("```"):
    lines = text.splitlines()
    if len(lines) >= 3:
      return "\n".join(lines[1:-1]).strip()
  return text


def _truncate_content(content: str, limit: int = 500) -> str:
  return content if len(content) <= limit else content[:limit] + "…"


def _persist_debug_payload(
  image_path: str,
  page_number: int,
  raw_content: str,
  payload: Dict[str, Any],
  used_json_mode: bool,
) -> None:
  try:
    image_file = Path(image_path)
    debug_file = image_file.with_name(f"{image_file.stem}-model-debug.json")
    debug_file.write_text(
      json.dumps(
        {
          "page": page_number,
          "usedJsonMode": used_json_mode,
          "rawContent": raw_content,
          "parsedPayload": payload,
        },
        indent=2,
      ),
      encoding="utf-8",
    )
  except Exception as exc:  # pragma: no cover - debug helper best effort
    logger.debug("Failed to persist debug payload for %s: %s", image_path, exc)


def parse_fields(page_number: int, payload: Dict[str, Any]) -> List[FieldExtraction]:
  fields_data = payload.get("fields") or []
  results: List[FieldExtraction] = []
  for index, item in enumerate(fields_data):
    if not isinstance(item, dict):
      continue
    bbox = _parse_bbox(item.get("bbox"))
    confidence = _quantize_confidence(_safe_float(item.get("confidence"))) or 0.0
    field_id = item.get("id") or f"field-{page_number}-{index + 1}"
    name = str(item.get("name") or f"Field {index + 1}")
    value = str(item.get("value") or "")
    results.append(
      FieldExtraction(
        id=field_id,
        page=page_number,
        name=name,
        value=value,
        confidence=confidence,
        bbox=bbox,
        source_type=item.get("sourceType"),
      )
    )
  return results


def parse_tables(page_number: int, payload: Dict[str, Any]) -> List[TableExtraction]:
  tables_data = payload.get("tables") or []
  tables: List[TableExtraction] = []

  for index, item in enumerate(tables_data):
    if not isinstance(item, dict):
      continue

    table_id = item.get("id") or f"table-{page_number}-{index + 1}"
    columns_payload = item.get("columns") or []
    rows_payload = item.get("rows") or []

    if isinstance(columns_payload, dict):
      columns_payload = list(columns_payload.values())
    if isinstance(rows_payload, dict):
      rows_payload = list(rows_payload.values())

    rows: List[List[TableCell]] = []
    columns: List[TableColumn] = []
    column_lookup: Dict[str, int] = {}

    def ensure_column(
      header: Any,
      *,
      key: Optional[str] = None,
      confidence: Optional[Any] = None,
      column_type: Optional[str] = None,
    ) -> TableColumn:
      header_text = str(header or key or f"Column {len(columns) + 1}").strip()
      if not header_text:
        header_text = f"Column {len(columns) + 1}"
      normalized_key = _normalize_column_name(key) if key else _normalize_column_name(header_text)

      lookup_keys = [normalized_key, _normalize_column_name(header_text)]
      for candidate in list(lookup_keys):
        if candidate and candidate in column_lookup:
          existing = columns[column_lookup[candidate]]
          quant_conf = _quantize_confidence(_safe_float(confidence))
          if quant_conf is not None:
            existing.confidence = quant_conf
          if column_type and not existing.type:
            existing.type = column_type
          return existing

      key_for_column = normalized_key or f"col_{len(columns)}"
      column = TableColumn(
        key=key_for_column,
        header=header_text,
        type=column_type,
        confidence=_quantize_confidence(_safe_float(confidence)),
      )
      columns.append(column)
      column_index = len(columns) - 1

      for candidate in lookup_keys + [column.key, _normalize_column_name(column.key)]:
        if candidate:
          column_lookup[candidate] = column_index

      # Pad previously parsed rows with empty cells when a new column appears later.
      if rows:
        for existing_row in rows:
          existing_row.append(TableCell(value=""))

      return column

    def parse_cell(cell: Any) -> TableCell:
      if isinstance(cell, dict):
        raw_value = cell.get("value")
        if raw_value is None:
          raw_value = cell.get("text") or cell.get("content")
        if isinstance(raw_value, list):
          raw_value = ", ".join(str(item) for item in raw_value if item is not None)
        value = "" if raw_value is None else str(raw_value)
        return TableCell(
          value=value,
          confidence=_quantize_confidence(_safe_float(cell.get("confidence"))),
          bbox=_parse_bbox(cell.get("bbox")),
        )

      if isinstance(cell, list):
        value = ", ".join(str(item) for item in cell if item is not None)
        return TableCell(value=value)

      if cell is None:
        return TableCell(value="")

      return TableCell(value=str(cell))

    # Prime columns from the payload when they are provided explicitly.
    for column_index, column in enumerate(columns_payload):
      if isinstance(column, dict):
        ensure_column(
          column.get("header") or column.get("name") or column.get("key") or f"Column {column_index + 1}",
          key=column.get("key"),
          confidence=column.get("confidence"),
          column_type=column.get("type"),
        )
      elif isinstance(column, str):
        ensure_column(column)
      else:
        ensure_column(f"Column {column_index + 1}")

    for row in rows_payload:
      if isinstance(row, list):
        if not row:
          continue
        while len(columns) < len(row):
          ensure_column(f"Column {len(columns) + 1}")

        parsed_row = [parse_cell(cell) for cell in row]
        if len(parsed_row) < len(columns):
          parsed_row.extend(TableCell(value="") for _ in range(len(columns) - len(parsed_row)))
        rows.append(parsed_row)
        continue

      if isinstance(row, dict):
        if not row:
          continue

        for raw_key in row.keys():
          ensure_column(raw_key)

        normalized_row_keys = {_normalize_column_name(key): key for key in row.keys()}
        parsed_row: List[TableCell] = []

        for column in columns:
          candidate_keys = [column.key, column.header]
          matched_key: Optional[str] = None
          for candidate in candidate_keys:
            normalized = _normalize_column_name(candidate)
            if normalized in normalized_row_keys:
              matched_key = normalized_row_keys[normalized]
              break
          cell_value = row.get(matched_key) if matched_key else None
          parsed_row.append(parse_cell(cell_value))

        rows.append(parsed_row)

    tables.append(
      TableExtraction(
        id=table_id,
        page=page_number,
        caption=item.get("caption"),
        confidence=_quantize_confidence(_safe_float(item.get("confidence"))),
        columns=columns,
        rows=rows,
        bbox=_parse_bbox(item.get("bbox")),
        normalized=True,
      )
    )

  return tables
