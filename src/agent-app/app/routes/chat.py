from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from opentelemetry import trace

from app.config import Settings, get_settings
from app.models import ChatRequest, ChatResponse
from app.services.foundry_client import FoundryGatewayClient

router = APIRouter(prefix="", tags=["chat"])
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


def get_foundry_client(settings: Settings = Depends(get_settings)) -> FoundryGatewayClient:
    return FoundryGatewayClient(settings)


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    request: ChatRequest,
    client: FoundryGatewayClient = Depends(get_foundry_client),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """
    Send a chat completion request through the APIM AI Gateway to Azure AI Foundry.

    The APIM gateway:
    - Authenticates to Foundry via Managed Identity
    - Enforces token quotas per product tier
    - Emits token usage metrics to Azure Monitor
    - Propagates x-correlation-id end-to-end
    """
    current_span = trace.get_current_span()
    current_span.set_attribute("chat.tenant_id", settings.app_tenant_id)
    current_span.set_attribute("chat.consumer_name", settings.app_consumer_name)
    current_span.set_attribute("chat.message_count", len(request.messages))

    try:
        response = await client.chat_completion(request)
    except Exception as exc:
        logger.exception("Chat completion failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream error: {type(exc).__name__}",
        ) from exc
    finally:
        await client.aclose()

    return response
