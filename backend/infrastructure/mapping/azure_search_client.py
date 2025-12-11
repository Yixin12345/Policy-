"""Lightweight Azure AI Search adapter for policy conversion mapping."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Sequence

import requests

from backend.config import get_settings
from backend.domain.value_objects.canonical_field import CanonicalField

logger = logging.getLogger(__name__)


class AzureSearchClient:
    """Query Azure AI Search for field-aligned snippets."""

    def __init__(self) -> None:
        settings = get_settings()
        self._endpoint = (settings.azure_search_endpoint or "").rstrip("/")
        self._index = settings.azure_search_index_name
        self._api_key = settings.azure_search_api_key

    @property
    def is_configured(self) -> bool:
        return bool(self._endpoint and self._index and self._api_key)

    def search_fields(
        self,
        *,
        fields: Sequence[CanonicalField],
        job_id: str,
        top_k: int = 5,
    ) -> Dict[str, List[dict]]:
        """Return top-K hits per canonical field identifier."""

        if not self.is_configured:
            logger.info("Azure Search not configured; skipping search enrichment")
            return {}

        headers = {
            "Content-Type": "application/json",
            "api-key": self._api_key or "",
        }
        results: Dict[str, List[dict]] = {}
        for field in fields:
            # Include both the canonical label and description in the search text to
            # increase recall when snippets are stored with descriptive phrasing.
            search_terms = [field.label]
            if getattr(field, "description", None):
                search_terms.append(field.description)

            payload = {
                "search": " ".join(search_terms),
                "queryType": "simple",
                "top": top_k,
                "filter": f"jobId eq '{job_id}'",
                "select": "page,text,fieldId,tableId,column",
            }
            url = f"{self._endpoint}/indexes/{self._index}/docs/search?api-version=2024-05-01-preview"
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                hits: List[dict] = []
                for raw in data.get("value", []):
                    hits.append(
                        {
                            "text": raw.get("text") or raw.get("content"),
                            "score": raw.get("@search.score"),
                            "page": raw.get("page"),
                            "field_id": raw.get("fieldId"),
                            "table_id": raw.get("tableId"),
                            "column": raw.get("column"),
                        }
                    )
                if hits:
                    results[field.identifier] = hits
            except Exception as exc:  # pragma: no cover - log and continue
                logger.warning("Azure Search query failed for %s: %s", field.label, exc)
        return results
