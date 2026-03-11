from __future__ import annotations

import hashlib
import json
import logging

import httpx
from azure.identity import DefaultAzureCredential
from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode

from app.config import Settings
from app.models import ChatRequest, ChatResponse, ChatMessage, ChatChoice, TokenUsage

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# Cognitive Services audience for DefaultAzureCredential token acquisition
# Used only if the app calls Foundry directly (bypassing APIM) in local dev.
_COGNITIVE_SERVICES_AUDIENCE = "https://cognitiveservices.azure.com/.default"


class FoundryGatewayClient:
    """
    HTTP client that routes chat completion requests through the APIM AI Gateway.

    Authentication to APIM uses an APIM subscription key.
    Authentication from APIM to Foundry is handled by APIM via Managed Identity
    – the client never needs a Foundry API key.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.apim_gateway_url,
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0),
            headers={
                "Content-Type": "application/json",
                "Ocp-Apim-Subscription-Key": settings.apim_subscription_key,
                "x-tenant-id": settings.app_tenant_id,
                "x-consumer-name": settings.app_consumer_name,
            },
        )

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        model = request.model or self._settings.default_model_deployment
        max_tokens = request.max_tokens or self._settings.max_tokens
        temperature = request.temperature if request.temperature is not None else self._settings.temperature

        with tracer.start_as_current_span(
            "gen_ai.chat",
            kind=SpanKind.CLIENT,
        ) as span:
            # GenAI semantic convention attributes
            span.set_attribute("gen_ai.system", "az.ai.inference")
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.request.max_tokens", max_tokens)
            span.set_attribute("gen_ai.request.temperature", temperature)
            span.set_attribute("server.address", self._settings.apim_gateway_url)

            # Attach message hash / redact as configured
            self._record_request_content(span, request.messages)

            payload = {
                "messages": [m.model_dump() for m in request.messages],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }

            try:
                response = await self._http.post(
                    f"/openai/deployments/{model}/chat/completions?api-version=2024-12-01-preview",
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise
            except httpx.RequestError as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise

            data = response.json()
            correlation_id = response.headers.get("x-correlation-id", "")

            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)

            # GenAI semantic convention – token usage attributes
            span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
            span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
            span.set_attribute("gen_ai.response.model", data.get("model", model))

            finish_reasons = [
                c.get("finish_reason") for c in data.get("choices", [])
                if c.get("finish_reason")
            ]
            if finish_reasons:
                span.set_attribute("gen_ai.response.finish_reasons", finish_reasons)

            span.set_attribute("custom.correlation_id", correlation_id)
            span.set_attribute("custom.tenant_id", self._settings.app_tenant_id)
            span.set_attribute("custom.consumer_name", self._settings.app_consumer_name)
            span.set_status(StatusCode.OK)

            choices = [
                ChatChoice(
                    index=c.get("index", 0),
                    message=ChatMessage(
                        role=c["message"]["role"],
                        content=c["message"]["content"],
                    ),
                    finish_reason=c.get("finish_reason"),
                )
                for c in data.get("choices", [])
            ]

            return ChatResponse(
                id=data.get("id", ""),
                model=data.get("model", model),
                choices=choices,
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                ),
                correlation_id=correlation_id,
            )

    def _record_request_content(
        self, span: trace.Span, messages: list[ChatMessage]
    ) -> None:
        """Attach message information to the span according to privacy settings."""
        if self._settings.log_content_redact_enabled:
            span.set_attribute("gen_ai.request.messages", "[REDACTED]")
            return
        if self._settings.log_content_hash_enabled:
            payload = json.dumps(
                [m.model_dump() for m in messages], sort_keys=True, ensure_ascii=True
            )
            digest = hashlib.sha256(payload.encode()).hexdigest()
            span.set_attribute("gen_ai.request.body_hash", digest)
            return
        # If neither flag is set, do not attach content at all.

    async def aclose(self) -> None:
        await self._http.aclose()
