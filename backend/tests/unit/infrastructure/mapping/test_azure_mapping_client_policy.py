import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.domain.entities.job import Job
from backend.domain.entities.job_status import JobState, JobStatus
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.services.canonical_mapper import CanonicalMapper
from backend.infrastructure.mapping.azure_mapping_client import AzureMappingClient
from backend.infrastructure.mapping.azure_search_client import AzureSearchClient
from backend.infrastructure.mapping.canonical_transformer import CanonicalTransformer
from backend.infrastructure.mapping.prompt_builder import CanonicalPromptBuilder


@dataclass
class _FakeMessage:
    content: str
    parsed: Optional[Dict[str, Any]] = None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: List[_FakeChoice]


class _FakeChat:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def completions(self) -> "_FakeChat":
        return self

    def create(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content=json.dumps(self._payload)))])


class _FakeOpenAI:
    def __init__(self, payload: dict) -> None:
        self.chat = _FakeChat(payload)  # type: ignore[attr-defined]


class _FakeSearch(AzureSearchClient):
    def __init__(self, hits: Dict[str, List[dict]]) -> None:
        super().__init__()
        self._hits = hits

    @property
    def is_configured(self) -> bool:  # pragma: no cover - simplify for test
        return True

    def search_fields(self, *, fields, job_id: str, top_k: int = 3):  # type: ignore[override]
        return self._hits


def _make_job() -> Job:
    status = JobStatus(job_id="job-1", total_pages=1, state=JobState.COMPLETED)
    page = PageExtraction.create(page_number=1, fields=[], tables=[])
    return Job(job_id="job-1", filename="policy.pdf", status=status, total_pages=1, pages=[page])


def test_mapping_merges_search_hits_and_llm_payload():
    llm_payload = {
        "policyConversion": {
            "Maximum Lifetime $Benefit": {"value": "$200,000", "confidence": 0.77, "sources": [{"page": 1}]},
            "Benefit Type": {"value": None, "confidence": None, "sources": []},
        },
        "schemaVersion": "test",
    }
    fake_client = _FakeOpenAI(llm_payload)
    search_hits = {"BENEFIT_TYPE": [{"text": "Comprehensive", "score": 0.9, "page": 1}]}
    mapper = AzureMappingClient(
        client=fake_client,  # type: ignore[arg-type]
        transformer=CanonicalTransformer(),
        prompt_builder=CanonicalPromptBuilder(),
        mapper=CanonicalMapper(),
        search_client=_FakeSearch(search_hits),
    )
    job = _make_job()
    result = mapper.generate(job)

    bundle = result.canonical
    assert bundle["policyConversion"]["Benefit Type"]["value"] == "Comprehensive"
    assert bundle["policyConversion"]["Maximum Lifetime $Benefit"]["value"] == "$200,000"
