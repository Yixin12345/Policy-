"""Tests for AzureMappingClient integrations."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.infrastructure.mapping.azure_mapping_client import (
    AzureMappingClient,
)


class _DummyChatCompletions:
    def __init__(self, response_json: Dict[str, Any], *, parsed: Optional[Dict[str, Any]] = None, as_content_list: bool = False) -> None:
        self._response_json = response_json
        self._parsed = parsed
        self._as_content_list = as_content_list
        self.last_kwargs: Optional[Dict[str, Any]] = None

    def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        payload = self._response_json_json()
        content: Any
        if self._as_content_list:
            content = [
                SimpleNamespace(type="text", text=payload)
            ]
        else:
            content = payload
        message = SimpleNamespace(content=content, parsed=self._parsed)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    def _response_json_json(self) -> str:
        import json

        return json.dumps(self._response_json)


class _DummyChat:
    def __init__(self, completions: _DummyChatCompletions) -> None:
        self.completions = completions


class _DummyOpenAI:
    def __init__(self, response_json: Dict[str, Any], *, parsed: Optional[Dict[str, Any]] = None, as_content_list: bool = False) -> None:
        self._completions = _DummyChatCompletions(response_json=response_json, parsed=parsed, as_content_list=as_content_list)
        self.chat = _DummyChat(self._completions)

    @property
    def completions(self) -> _DummyChatCompletions:
        return self._completions


def _make_job() -> tuple[Job, FieldExtraction]:
    job = Job.create(job_id="job-001", filename="test.pdf")
    field = FieldExtraction.create(
        field_name="policy number",
        value="PN-001",
        confidence=0.92,
        page_number=1,
    )
    page = PageExtraction.create(page_number=1, fields=[field], tables=[])
    return job.with_pages([page]), field


def test_generate_uses_deterministic_skeleton_and_merges_values() -> None:
    dummy_response = {
        "documentTypes": ["facility_invoice"],
        "invoice": {
            "Policy number": {
                "value": "PN-LLM",
                "confidence": 0.3,
                "sources": [{"fieldId": "llm"}],
            }
        },
        "reasoningNotes": ["LLM attempted overwrite"],
    }
    dummy_client = _DummyOpenAI(response_json=dummy_response)
    azure_client = AzureMappingClient(client=dummy_client)

    job, field = _make_job()
    metadata = {
        "documentCategories": ["facility_invoice"],
        "pageCategories": {1: "facility_invoice"},
    }

    result = azure_client.generate(job, metadata=metadata)

    policy_entry = result.canonical["invoice"]["Policy number"]
    assert policy_entry["value"] == "PN-001"
    assert policy_entry["confidence"] == 0.92
    source_field_ids = {source.get("fieldId") for source in policy_entry.get("sources", [])}
    assert str(field.id) in source_field_ids
    assert "llm" in source_field_ids

    assert result.canonical["documentTypes"] == ["facility_invoice"]
    assert "deterministic" in result.trace

    messages: List[Dict[str, Any]] = dummy_client.completions.last_kwargs["messages"]
    assert "Output requirements" in messages[1]["content"][0]["text"]
    assert "Deterministic canonical skeleton" in messages[1]["content"][1]["text"]
    assert "Policy number" in messages[1]["content"][2]["text"]
    assert result.trace["prompt"]["documentCategories"] == ["facility_invoice"]
    assert result.trace["prompt"]["pageCategories"] == {1: "facility_invoice"}


def test_generate_supports_parsed_payload() -> None:
    dummy_response = {
        "documentTypes": ["facility_invoice"],
        "invoice": {
            "Policy number": {
                "value": "PN-Parsed",
                "confidence": 0.5,
                "sources": [{"fieldId": "llm"}],
            }
        },
    }

    dummy_client = _DummyOpenAI(response_json=dummy_response, parsed=dummy_response)
    azure_client = AzureMappingClient(client=dummy_client)

    job, _ = _make_job()
    result = azure_client.generate(job)

    sources = result.canonical["invoice"]["Policy number"].get("sources", [])
    assert any(source.get("fieldId") == "llm" for source in sources)
    assert "PN-Parsed" in result.trace["response"]


def test_generate_handles_list_content_payload() -> None:
    dummy_response = {
        "documentTypes": ["facility_invoice"],
        "invoice": {
            "Policy number": {
                "value": "PN-List",
                "confidence": 0.4,
                "sources": [{"fieldId": "llm"}],
            }
        },
    }

    dummy_client = _DummyOpenAI(response_json=dummy_response, as_content_list=True)
    azure_client = AzureMappingClient(client=dummy_client)

    job, _ = _make_job()
    result = azure_client.generate(job)

    sources = result.canonical["invoice"]["Policy number"].get("sources", [])
    assert any(source.get("fieldId") == "llm" for source in sources)
    assert "PN-List" in result.trace["response"]