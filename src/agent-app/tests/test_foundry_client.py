from __future__ import annotations

import json
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pytest import MonkeyPatch

from app.config import Settings
from app.models import ChatMessage, ChatRequest
from app.services.foundry_client import FoundryGatewayClient


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        apim_gateway_url="http://mock-apim",
        apim_subscription_key="test-key",
        app_tenant_id="tenant-test",
        app_consumer_name="test-agent",
        log_content_hash_enabled=True,
        log_content_redact_enabled=False,
        applicationinsights_connection_string="",
    )


@pytest.fixture()
def mock_response_data() -> dict:
    return {
        "id": "chatcmpl-abc",
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Token metering is crucial for cost control."},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "total_tokens": 30,
        },
    }


@pytest.mark.asyncio
async def test_chat_completion_success(
    settings: Settings, mock_response_data: dict
) -> None:
    client = FoundryGatewayClient(settings)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.json.return_value = mock_response_data
    mock_resp.headers = {"x-correlation-id": "corr-123"}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")]
        )
        response = await client.chat_completion(request)

    assert response.id == "chatcmpl-abc"
    assert response.usage.total_tokens == 30
    assert response.correlation_id == "corr-123"
    await client.aclose()


@pytest.mark.asyncio
async def test_chat_completion_http_error(settings: Settings) -> None:
    client = FoundryGatewayClient(settings)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(),
        response=mock_resp,
    )

    with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
        request = ChatRequest(messages=[ChatMessage(role="user", content="Hello")])
        with pytest.raises(httpx.HTTPStatusError):
            await client.chat_completion(request)
    await client.aclose()


def test_record_request_hash(settings: Settings) -> None:
    client = FoundryGatewayClient(settings)
    messages = [ChatMessage(role="user", content="hello")]
    span = MagicMock()
    client._record_request_content(span, messages)
    # Should call set_attribute with the SHA-256 hash
    calls = {call[0][0]: call[0][1] for call in span.set_attribute.call_args_list}
    assert "gen_ai.request.body_hash" in calls
    expected = hashlib.sha256(
        json.dumps([{"role": "user", "content": "hello"}], sort_keys=True, ensure_ascii=True).encode()
    ).hexdigest()
    assert calls["gen_ai.request.body_hash"] == expected


def test_record_request_redacted() -> None:
    s = Settings(
        apim_gateway_url="http://mock-apim",
        log_content_redact_enabled=True,
        applicationinsights_connection_string="",
    )
    client = FoundryGatewayClient(s)
    span = MagicMock()
    client._record_request_content(span, [ChatMessage(role="user", content="secret")])
    calls = {call[0][0]: call[0][1] for call in span.set_attribute.call_args_list}
    assert calls["gen_ai.request.messages"] == "[REDACTED]"
