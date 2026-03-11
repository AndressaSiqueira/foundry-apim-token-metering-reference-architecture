from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str = Field(..., min_length=1, max_length=32_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=50)
    model: str | None = None  # Overrides default deployment if provided
    max_tokens: Annotated[int, Field(ge=1, le=16_384)] | None = None
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] | None = None
    stream: bool = False

    @field_validator("messages")
    @classmethod
    def validate_first_message(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        if not v:
            raise ValueError("messages must not be empty")
        return v


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Chatchoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str | None = None


class ChatResponse(BaseModel):
    id: str
    model: str
    choices: list[ChatChoice]
    usage: TokenUsage
    correlation_id: str = ""


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str | None = None


# Re-export clean
__all__ = ["ChatMessage", "ChatRequest", "TokenUsage", "ChatChoice", "ChatResponse"]
