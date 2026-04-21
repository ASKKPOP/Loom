"""Pydantic request/response models matching OpenAI's Chat Completions API.

Implements the subset vMLX 0.1 supports: model, messages, max_tokens,
temperature, top_p, stream, stop, n=1. Extra fields in requests are
accepted but ignored (OpenAI SDKs may send fields we don't use yet).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str

    model_config = ConfigDict(extra="ignore")


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    max_tokens: int | None = Field(default=None, gt=0, le=32_768)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    stream: bool = False
    stop: str | list[str] | None = None
    n: int = 1

    model_config = ConfigDict(extra="ignore")


class ChoiceMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    index: int
    message: ChoiceMessage
    finish_reason: str | None


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage


# ─── Streaming (chunk) shape ────────────────────────────────────────


class ChoiceDelta(BaseModel):
    role: Literal["assistant"] | None = None
    content: str | None = None


class ChunkChoice(BaseModel):
    index: int
    delta: ChoiceDelta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChunkChoice]


# ─── Models listing ─────────────────────────────────────────────────


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "vmlx"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]
