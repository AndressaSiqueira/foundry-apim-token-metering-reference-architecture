from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import ChatMessage, ChatResponse, ChatChoice, TokenUsage


@pytest.fixture(autouse=True)
def mock_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable OTel telemetry setup in tests."""
    monkeypatch.setattr("app.main.setup_telemetry", lambda _: None)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def mock_chat_response() -> ChatResponse:
    return ChatResponse(
        id="chatcmpl-test-123",
        model="gpt-4o",
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content="Token metering routes every AI call through APIM."),
                finish_reason="stop",
            )
        ],
        usage=TokenUsage(prompt_tokens=15, completion_tokens=12, total_tokens=27),
        correlation_id="test-corr-id",
    )


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_success(
    client: TestClient, mock_chat_response: ChatResponse
) -> None:
    with patch(
        "app.routes.chat.FoundryGatewayClient.chat_completion",
        new_callable=AsyncMock,
        return_value=mock_chat_response,
    ):
        response = client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hello, explain token metering."}]
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "chatcmpl-test-123"
    assert data["usage"]["total_tokens"] == 27
    assert len(data["choices"]) == 1


def test_chat_empty_messages(client: TestClient) -> None:
    response = client.post("/chat", json={"messages": []})
    assert response.status_code == 422


def test_chat_missing_content(client: TestClient) -> None:
    response = client.post("/chat", json={"messages": [{"role": "user"}]})
    assert response.status_code == 422


def test_chat_upstream_error(client: TestClient) -> None:
    import httpx

    with patch(
        "app.routes.chat.FoundryGatewayClient.chat_completion",
        new_callable=AsyncMock,
        side_effect=httpx.RequestError("Connection refused"),
    ):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
    assert response.status_code == 502
    assert "Upstream error" in response.json()["detail"]
