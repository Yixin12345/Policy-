"""Utilities for constructing Azure OpenAI vision prompts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

DEFAULT_PROMPT_TEMPLATE = (
    "You are an expert document extraction system. Analyze the document image and return structured JSON only. Your primary goals are:"
    " (1) classify the document page into one of ['policy_conversion','other'];"
    " (2) extract field name/value pairs;"
    " (3) extract table structures."
    " You may need to account for sideways table layouts or handwritten notes."
    " Use this exact JSON schema for your response: {\n"
    "  \"documentType\": {\n"
    "    \"label\": string from ['policy_conversion','other'],\n"
    "    \"confidence\": number between 0 and 1,\n"
    "    \"reasons\": [string]\n"
    "  },\n"
    "  \"fields\": [\n"
    "    {\"id\": string, \"name\": string, \"value\": string, \"confidence\": number between 0 and 1, \"sourceType\": string optional,"
    "     \"bbox\": {\"x\": number between 0 and 1, \"y\": number between 0 and 1, \"width\": number between 0 and 1, \"height\": number between 0 and 1} }\n"
    "  ],\n"
    "  \"tables\": [\n"
    "    {\n"
    "      \"id\": string,\n"
    "      \"caption\": string or null,\n"
    "      \"confidence\": number between 0 and 1,\n"
    "      \"columns\": [{ \"key\": string, \"header\": string, \"type\": string optional, \"confidence\": number optional }],\n"
    "      \"rows\": [[{ \"value\": string, \"confidence\": number optional, \"bbox\": {\"x\": number between 0 and 1, \"y\": number between 0 and 1, \"width\": number between 0 and 1, \"height\": number between 0 and 1} }]]\n"
    "    }\n"
    "  ]\n"
    "}.\n"
    "All bbox coordinates must be provided and normalised to the [0,1] range relative to the page width/height. Use very small non-zero widths/heights for point-like selections instead of omitting the bbox. Confidence values for fields, tables, and the documentType must be chosen from [0.0, 0.2, 0.4, 0.6, 0.8, 1.0] (0.0 = unreadable, 1.0 = exact match)."
    "Do not add commentary. If nothing is found return {\"documentType\":{\"label\":\"other\",\"confidence\":0.0,\"reasons\":[]},\"fields\":[],\"tables\":[]}."
)


@dataclass(frozen=True)
class VisionPromptAttempt:
    """Encapsulates a single attempt payload for the vision model."""

    messages: List[dict[str, Any]]
    force_json: bool


def build_prompt_attempts(page_number: int, image_data_url: str) -> List[VisionPromptAttempt]:
    """Construct prompt attempts for a page image.

    The Azure OpenAI vision model can occasionally miss returning JSON, so we
    prepare multiple attempts: first with forced JSON output, then with relaxed
    formatting, and finally with a clarifying instruction.
    """

    base_messages = [
        {"role": "system", "content": DEFAULT_PROMPT_TEMPLATE},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Perform OCR to extract field-value pair data and table data for page {page_number}.",
                },
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]

    relaxed_messages = [
        base_messages[0],
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Perform OCR to extract field-value pair data and table data for this page."
                        " If no structured data can be extracted, reply with an empty fields/tables array."
                    ),
                },
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]

    return [
        VisionPromptAttempt(messages=base_messages, force_json=True),
        VisionPromptAttempt(messages=base_messages, force_json=False),
        VisionPromptAttempt(messages=relaxed_messages, force_json=False),
    ]
