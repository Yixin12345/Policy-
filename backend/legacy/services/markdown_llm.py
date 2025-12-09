from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from backend.config import get_settings

logger = logging.getLogger(__name__)

_PAGE_SPLIT_PATTERN = re.compile(r"^\s*<---\s*Page\s+Split\s*--->\s*$", re.MULTILINE)

_CLIENT: Optional[AzureOpenAI] = None
_MODEL: Optional[str] = None

_PAGE_EXTRACTION_SYSTEM_PROMPT = """
You are an expert Markdown interpreter producing structured OCR output. The user provides Markdown generated from a document page. Each content span contains detector tokens like <|ref|>LABEL<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|> followed by text.

For every field or table you find, recover the bounding box coordinates from the associated detector token. Treat the coordinates as pixel values where x1,y1 are the top-left corner and x2,y2 are the bottom-right corner. Preserve the raw detector coordinates without normalizing them; return x, y, width, height as integers computed from (x1, y1, x2, y2) using width = x2 - x1 and height = y2 - y1.

Return JSON with this schema:
{
  "pageNumber": <int>,
  "pageWidth": <int>,
  "pageHeight": <int>,
  "documentType": {
    "label": "facility_invoice" | "cmr_form" | "ub04" | "other",
    "confidence": one of [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    "reasons": [string]
  },
  "fields": [
    {
      "id": string,
      "name": string,
      "value": string,
      "confidence": one of [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
      "sourceType": string | null,
    "bbox": {"x": int, "y": int, "width": int, "height": int}
    }
  ],
  "tables": [
    {
      "id": string,
      "caption": string | null,
      "confidence": one of [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
      "columns": [{"key": string, "header": string, "type": string | null, "confidence": float | null}],
    "rows": [[{"value": string, "confidence": float | null, "bbox": {"x": int, "y": int, "width": int, "height": int}}]]
    }
  ]
}

Only emit JSON, no markdown fences or commentary.
""".strip()

@dataclass(frozen=True)
class PageExtractionPayload:
    payload: Dict[str, Any]
    raw: str


def split_markdown_pages(markdown_text: str) -> List[str]:
    parts = [part.strip() for part in _PAGE_SPLIT_PATTERN.split(markdown_text)]
    filtered = [part for part in parts if part]
    return filtered or [markdown_text]


def preprocess_markdown_for_bbox(page_text: str) -> str:
    ref_det_pattern = re.compile(r"<\|ref\|>.*?<\|/ref\|>\s*<\|det\|>(\[\[.*?\]\])<\|/det\|>")
    table_start_pattern = re.compile(r"<table>")
    table_end_pattern = re.compile(r"</table>")
    lines = page_text.splitlines()
    processed_lines = []
    in_table = False
    for line in lines:
        if table_start_pattern.search(line):
            in_table = True
        if in_table:
            processed_lines.append(line)
            if table_end_pattern.search(line):
                in_table = False
            continue
        match = ref_det_pattern.search(line)
        if match:
            # Only keep the bounding box coordinates
            processed_lines.append(match.group(1))
        else:
            processed_lines.append(line)
    return "\n".join(processed_lines)

def extract_page_payload(page_text: str, page_number: int, debug_dir: Optional[Path] = None) -> PageExtractionPayload:
    client, model = _get_text_client()
    # Preprocess page_text for bounding boxes
    page_text = preprocess_markdown_for_bbox(page_text)
    messages = [
        {"role": "system", "content": _PAGE_EXTRACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Page number: {page_number}\n\n{page_text.strip()}",
        },
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
    )

    payload, raw = _coerce_json(response)
    payload.setdefault("pageNumber", page_number)
    payload.setdefault("fields", [])
    payload.setdefault("tables", [])
    payload.setdefault("documentType", {"label": "other", "confidence": 0.0, "reasons": []})

    if debug_dir is not None:
        _persist_debug(debug_dir / f"page-{page_number}-markdown-extraction.json", payload, raw)

    return PageExtractionPayload(payload=payload, raw=raw)



def _get_text_client() -> Tuple[AzureOpenAI, str]:
    global _CLIENT, _MODEL
    settings = get_settings()
    endpoint = settings.ensure_endpoint()
    model = (
        settings.azure_openai_text_model
        or settings.azure_openai_deployment_name
        or settings.azure_openai_vision_model
    )
    if not endpoint or not model:
        raise RuntimeError("Azure OpenAI configuration is incomplete for markdown processing")

    if _CLIENT is None:
        api_key = settings.azure_openai_api_key
        if api_key:
            _CLIENT = AzureOpenAI(
                api_key=api_key,
                api_version=settings.azure_openai_api_version,
                azure_endpoint=endpoint,
            )
        else:
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            _CLIENT = AzureOpenAI(
                api_version=settings.azure_openai_api_version,
                azure_endpoint=endpoint,
                azure_ad_token_provider=token_provider,
            )
    _MODEL = model
    return _CLIENT, model


def _coerce_json(response: Any) -> Tuple[Dict[str, Any], str]:
    if not response or not getattr(response, "choices", None):
        raise RuntimeError("Markdown LLM returned empty response")

    choice = response.choices[0]
    message = getattr(choice, "message", None)
    if message is None:
        raise RuntimeError("Markdown LLM response missing message")

    parsed = getattr(message, "parsed", None)
    if parsed:
        payload = json.loads(json.dumps(parsed))
        return payload, json.dumps(payload)

    content = getattr(message, "content", "")
    if isinstance(content, list):
        content = "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content)
    if not isinstance(content, str):
        content = str(content)
    text = content.strip()
    if not text:
        raise RuntimeError("Markdown LLM returned empty content")

    try:
        payload = json.loads(text)
        return payload, text
    except json.JSONDecodeError as exc:
        logger.exception("Failed to parse markdown LLM JSON: %s", text)
        raise RuntimeError("Markdown LLM returned invalid JSON") from exc


def _persist_debug(path: Path, payload: Dict[str, Any], raw: str, *, extra: Optional[Dict[str, Any]] = None) -> None:
    try:
        debug_payload = {"parsed": payload, "raw": raw}
        if extra:
            debug_payload["metadata"] = extra
        path.write_text(json.dumps(debug_payload, indent=2), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - best effort logging
        logger.debug("Failed to persist markdown debug payload %s: %s", path, exc)
