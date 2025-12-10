"""Azure OpenAI vision client adapter for the new infrastructure layer."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from backend.config import get_settings
from backend.infrastructure.pdf.image_processor import image_to_data_url

from .vision_prompt_builder import VisionPromptAttempt, build_prompt_attempts
from .vision_response_parser import VisionResponseParser

logger = logging.getLogger(__name__)


class VisionExtractionError(RuntimeError):
    """Raised when the vision model fails to produce a usable payload."""


@dataclass(frozen=True)
class VisionPageInput:
    """Information required to extract a single page."""

    page_number: int
    image_path: Path

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("page_number must be >= 1")
        if not isinstance(self.image_path, Path):
            object.__setattr__(self, "image_path", Path(self.image_path))


class AzureVisionClient:
    """High-level client responsible for orchestrating Azure OpenAI Vision calls."""

    def __init__(
        self,
        *,
        client: Optional[OpenAI] = None,
        parser: Optional[VisionResponseParser] = None,
    ) -> None:
        settings = get_settings()
        endpoint = settings.ensure_endpoint()
        model = settings.azure_openai_vision_model or settings.azure_openai_deployment_name

        if not endpoint:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT must be configured before using the vision client")
        if not model:
            raise RuntimeError("AZURE_OPENAI_VISION_MODEL or AZURE_OPENAI_DEPLOYMENT_NAME must be configured")

        if client is not None:
            self._client = client
        else:
            api_key = settings.azure_openai_api_key
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
        self._parser = parser or VisionResponseParser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_page(self, page: VisionPageInput) -> Optional[dict]:
        """Extract structured data for a single page image.

        Returns a dictionary representation of :class:`PageExtraction` to keep
        compatibility with the application layer, which still expects raw
        dictionaries when hydrating domain entities.
        """

        attempts = build_prompt_attempts(page.page_number, image_to_data_url(page.image_path))
        payload = self._run_attempts(attempts)
        if payload is None:
            logger.error("Vision model returned no payload for page %s", page.page_number)
            return None

        domain_page = self._parser.parse_page(
            page_number=page.page_number,
            payload=payload,
            image_path=str(page.image_path),
        )
        return domain_page.to_dict()

    def extract_document(self, pages: Iterable[VisionPageInput]) -> List[dict]:
        """Extract structured data for a sequence of page images."""

        results: List[dict] = []
        for page in pages:
            page_result = self.extract_page(page)
            if page_result is not None:
                results.append(page_result)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _run_attempts(self, attempts: Iterable[VisionPromptAttempt]) -> Optional[dict]:
        content: Optional[str] = None
        last_attempt_forced_json = False

        for attempt in attempts:
            content, last_attempt_forced_json = self._invoke_model(attempt)
            if content:
                payload = self._extract_json_payload(content)
                if payload is not None:
                    return payload
                logger.debug(
                    "Vision attempt yielded invalid JSON (force_json=%s): %.200s",
                    attempt.force_json,
                    content,
                )

        if content:
            logger.warning(
                "Failed to parse vision payload after retries (force_json=%s).", last_attempt_forced_json
            )
        return None

    def _invoke_model(self, attempt: VisionPromptAttempt) -> tuple[Optional[str], bool]:
        kwargs = {
            "model": self._model,
            "messages": attempt.messages,
            "max_completion_tokens": 50000,
        }
        if attempt.force_json:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content if response.choices else None
        return content or None, attempt.force_json

    @staticmethod
    def _extract_json_payload(content: str) -> Optional[dict]:
        text = content.strip()
        if not text:
            return None

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Handle fenced code blocks
        if text.startswith("```") and text.endswith("```"):
            body = "\n".join(text.splitlines()[1:-1]).strip()
            if body:
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    pass

        # Fallback: attempt to locate first JSON object within the text
        start_index = text.find("{")
        end_index = text.rfind("}")
        if start_index != -1 and end_index != -1 and end_index > start_index:
            snippet = text[start_index : end_index + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                return None

        return None
