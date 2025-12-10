from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Ensure environment variables from the repository root .env are available
# regardless of the working directory used to start the process.
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseSettings):
  azure_openai_api_key: str | None = Field(default=None, alias="AZURE_OPENAI_API_KEY")
  azure_openai_endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
  azure_openai_api_version: str = Field(default="2024-12-01-preview", alias="AZURE_OPENAI_API_VERSION")
  azure_openai_deployment_name: str | None = Field(default=None, alias="AZURE_OPENAI_DEPLOYMENT_NAME")
  azure_openai_vision_model: str | None = Field(default=None, alias="AZURE_OPENAI_VISION_MODEL")
  azure_openai_text_model: str | None = Field(default=None, alias="AZURE_OPENAI_TEXT_MODEL")
  azure_search_endpoint: str | None = Field(default=None, alias="AZURE_SEARCH_ENDPOINT")
  azure_search_index_name: str | None = Field(default=None, alias="AZURE_SEARCH_INDEX")
  azure_search_api_key: str | None = Field(default=None, alias="AZURE_SEARCH_API_KEY")
  confidence_low_threshold: float = Field(default=0.4, alias="CONFIDENCE_LOW_THRESHOLD")

  def ensure_endpoint(self) -> str:
    endpoint = (self.azure_openai_endpoint or "").strip()
    if not endpoint:
        return ""
    return endpoint.rstrip("/") + "/"

  class Config:
    case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
  return Settings()  # type: ignore[arg-type]
