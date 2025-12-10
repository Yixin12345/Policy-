"""Query handler for canonical bundle generation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from backend.application.dto.canonical_dto import CanonicalBundleDTO
from backend.domain.exceptions import EntityNotFoundError
from backend.domain.repositories.job_repository import JobRepository
from backend.infrastructure.mapping.azure_mapping_client import (
    AzureMappingClient,
    MappingResult,
)

LegacyJobLoader = Optional[Callable[[str], Any]]


@dataclass(frozen=True)
class GetCanonicalBundleQuery:
    """Identify which job's canonical bundle to generate."""

    job_id: str


class GetCanonicalBundleHandler:
    """Generate canonical bundles for jobs using the mapping client."""

    def __init__(
        self,
        job_repository: JobRepository,
        mapping_client: AzureMappingClient,
        history_loader: LegacyJobLoader = None,
    ) -> None:
        self._jobs = job_repository
        self._mapping_client = mapping_client
        self._history_loader = history_loader

    def handle(self, query: GetCanonicalBundleQuery) -> CanonicalBundleDTO:
        job = self._jobs.find_by_id(query.job_id)
        if job is None:
            raise EntityNotFoundError("job", query.job_id)

        aggregated, table_groups, metadata, classifications = self._legacy_context(query.job_id)

        result = self._mapping_client.generate(
            job,
            aggregated=aggregated,
            table_groups=table_groups,
            metadata=metadata,
        )

        document_categories = self._merge_document_categories(
            result,
            metadata,
        )
        document_types = self._merge_document_types(result, metadata)
        page_categories = self._extract_page_categories(metadata)

        return CanonicalBundleDTO(
            job_id=job.job_id,
            canonical=result.canonical,
            trace=result.trace,
            document_categories=document_categories,
            document_types=document_types,
            page_categories=page_categories,
            page_classifications=classifications,
        )

    # ------------------------------------------------------------------
    # Legacy context helpers
    # ------------------------------------------------------------------
    def _legacy_context(
        self,
        job_id: str,
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        if self._history_loader is None:
            return None, None, None, []

        legacy_job = self._history_loader(job_id)
        if legacy_job is None:
            return None, None, None, []

        metadata = self._normalize_metadata(getattr(legacy_job, "metadata", None))
        aggregated = self._normalize_dict(getattr(legacy_job, "aggregated", None))
        table_groups = self._normalize_dict((metadata or {}).get("tableGroups"))

        if metadata is not None:
            if getattr(legacy_job, "document_type", None):
                metadata.setdefault("documentType", legacy_job.document_type)
            if getattr(legacy_job, "status", None) and getattr(legacy_job.status, "state", None):
                metadata.setdefault("jobState", getattr(legacy_job.status, "state", None))

        classifications = self._normalize_classifications((metadata or {}).get("pageClassifications"))

        return aggregated, table_groups, metadata, classifications

    @staticmethod
    def _normalize_dict(value: Any) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        if isinstance(value, dict):
            return dict(value)
        return None

    @staticmethod
    def _normalize_metadata(value: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(value, dict):
            return None
        normalized: Dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, dict):
                normalized[key] = dict(item)
            elif isinstance(item, (list, tuple)):
                normalized[key] = list(item)
            else:
                normalized[key] = item
        return normalized

    @staticmethod
    def _normalize_classifications(value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, Iterable):
            return []
        normalized: List[Dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                entry = dict(item)
            else:
                entry = {}
            page = entry.get("page")
            if isinstance(page, str) and page.isdigit():
                entry["page"] = int(page)
            normalized.append(entry)
        normalized.sort(key=lambda entry: entry.get("page", 0))
        return normalized

    # ------------------------------------------------------------------
    # Metadata merging helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _merge_document_categories(
        result: MappingResult,
        metadata: Optional[Dict[str, Any]],
    ) -> List[str]:
        categories: List[str] = []
        categories.extend(result.canonical.get("documentCategories", []))
        if metadata:
            raw = metadata.get("documentCategories")
            if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
                categories.extend(str(item) for item in raw if item)
            document_type = metadata.get("documentType")
            if isinstance(document_type, str) and document_type:
                categories.append(document_type)
        return _dedupe_preserve_order(categories)

    @staticmethod
    def _merge_document_types(
        result: MappingResult,
        metadata: Optional[Dict[str, Any]],
    ) -> List[str]:
        types: List[str] = []
        types.extend(result.canonical.get("documentTypes", []))
        if metadata:
            raw = metadata.get("documentTypes")
            if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
                types.extend(str(item) for item in raw if item)
            document_type = metadata.get("documentType")
            if isinstance(document_type, str) and document_type:
                types.append(document_type)
        return _dedupe_preserve_order(types)

    @staticmethod
    def _extract_page_categories(metadata: Optional[Dict[str, Any]]) -> Dict[int, str]:
        if not metadata:
            return {}
        raw = metadata.get("pageCategories")
        if not isinstance(raw, dict):
            return {}
        normalized: Dict[int, str] = {}
        for key, value in raw.items():
            try:
                page_index = int(key)
            except (TypeError, ValueError):
                continue
            if value is None:
                continue
            normalized[page_index] = str(value)
        return dict(sorted(normalized.items()))


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for item in items:
        token = str(item)
        normalized = token.lower()
        if not token or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(token)
    return deduped


__all__ = [
    "GetCanonicalBundleQuery",
    "GetCanonicalBundleHandler",
]
