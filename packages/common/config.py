"""
Sentinel — Shared configuration using pydantic-settings.
All settings are read from environment variables / infra/.env
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="infra/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # Database
    database_url: str = Field(default="postgresql://sentinel:sentinel_dev@localhost:5432/sentinel")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # LLM
    gemini_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    default_llm: str = Field(default="gemini")
    max_tokens: int = Field(default=1000)

    # Langfuse
    langfuse_secret_key: str = Field(default="")
    langfuse_public_key: str = Field(default="")
    langfuse_host: str = Field(default="http://localhost:3000")

    # HuggingFace
    hf_token: str = Field(default="")

    # News
    news_api_key: str = Field(default="")

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
