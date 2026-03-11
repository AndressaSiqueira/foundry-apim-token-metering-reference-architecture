from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables (/.env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- App identity -----
    otel_service_name: str = "foundry-agent-app"
    otel_service_version: str = "1.0.0"
    app_tenant_id: str = Field(default="unknown", description="Tenant ID sent as x-tenant-id header.")
    app_consumer_name: str = Field(default="agent-app", description="Consumer name sent as x-consumer-name header.")

    # ----- APIM gateway -----
    apim_gateway_url: str = Field(
        default="http://localhost:8001",
        description="Full base URL of the APIM gateway (no trailing slash).",
    )
    apim_subscription_key: str = Field(
        default="",
        description="APIM subscription key (Ocp-Apim-Subscription-Key header).",
    )

    # ----- Model defaults -----
    default_model_deployment: str = "gpt-4o"
    max_tokens: int = 2048
    temperature: float = 0.7
    enable_streaming: bool = False

    # ----- Azure Monitor / OTel -----
    applicationinsights_connection_string: str = Field(
        default="",
        description="App Insights connection string for Azure Monitor OTel exporter.",
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="",
        description="OTLP endpoint (used when connection string is not set).",
    )

    # ----- Privacy controls -----
    log_content_hash_enabled: bool = Field(
        default=True,
        description="Hash prompt/response with SHA-256 before attaching to spans.",
    )
    log_content_redact_enabled: bool = Field(
        default=False,
        description="Suppress all message content from spans (overrides hash).",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
