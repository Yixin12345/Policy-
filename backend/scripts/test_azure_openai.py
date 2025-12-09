#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import AzureOpenAI


PROMPT = "Reply with a friendly hello."


def main() -> int:
    load_dotenv()

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION") or "2025-01-01-preview"
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not endpoint or not deployment:
        print("Azure OpenAI endpoint and deployment name must be configured in the environment.", file=sys.stderr)
        return 1

    try:
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_version=api_version,
            api_key=api_key,
        )
    except Exception as exc:  # pragma: no cover - defensive hydration
        print(f"Failed to initialize Azure OpenAI client: {exc}", file=sys.stderr)
        return 1

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": PROMPT}],
        )
    except Exception as exc:
        print(f"Azure OpenAI request failed: {exc}", file=sys.stderr)
        return 1

    choice = response.choices[0].message if response.choices else None
    if not choice or not getattr(choice, "content", None):
        print("Azure OpenAI response did not include a message.", file=sys.stderr)
        return 1

    print(choice.content.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
