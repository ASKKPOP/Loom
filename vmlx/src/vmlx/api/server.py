"""FastAPI app exposing an OpenAI-compatible subset for vMLX.

Endpoints:

- ``GET  /v1/models``          — list loaded models
- ``POST /v1/chat/completions`` — non-streaming + SSE streaming
- ``GET  /health``              — liveness probe

The app takes an already-loaded engine protocol instance so tests can
inject stubs. Real runs use :func:`run_server` which builds + loads the
real engine under a FastAPI ``lifespan``.
"""

from __future__ import annotations

import contextlib
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Protocol

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from vmlx import __version__ as vmlx_version
from vmlx.api.openai_types import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    ChoiceDelta,
    ChoiceMessage,
    ChunkChoice,
    ModelCard,
    ModelList,
    Usage,
)
from vmlx.engine import GenerationResult, Message, StreamChunk


class ServerEngine(Protocol):
    """Structural type for anything the server can drive.

    Matches both :class:`vmlx.engine.SingleRequestEngine` and test stubs.
    """

    @property
    def model_id(self) -> str: ...

    def generate(
        self, prompt: str, *, max_tokens: int = ...
    ) -> GenerationResult: ...

    def stream_generate(
        self,
        messages: list[Message] | str,
        *,
        max_tokens: int = ...,
    ) -> Iterator[StreamChunk]: ...


def _chat_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


def _now() -> int:
    return int(time.time())


def _messages_from_request(req: ChatCompletionRequest) -> list[Message]:
    return [{"role": m.role, "content": m.content} for m in req.messages]


def create_app(engine: ServerEngine, *, default_max_tokens: int = 512) -> FastAPI:
    """Build the FastAPI app wired to a given engine instance.

    The engine must already be ``load()``-ed by the caller.
    """
    app = FastAPI(
        title="vMLX",
        version=vmlx_version,
        description="OpenAI-compatible local MLX serving (vMLX).",
    )

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "vmlx_version": vmlx_version})

    @app.get("/v1/models", response_model=ModelList)
    async def list_models() -> ModelList:
        return ModelList(data=[ModelCard(id=engine.model_id, created=0)])

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(
        body: ChatCompletionRequest,
    ) -> JSONResponse | StreamingResponse:
        messages = _messages_from_request(body)
        max_tokens = body.max_tokens or default_max_tokens

        if body.n != 1:
            raise HTTPException(
                status_code=400,
                detail="vmlx: only n=1 is supported in this release",
            )

        if body.stream:
            return _streaming_response(engine, body.model, messages, max_tokens)
        return _non_streaming_response(engine, body.model, messages, max_tokens)

    return app


def _non_streaming_response(
    engine: ServerEngine,
    request_model: str,
    messages: list[Message],
    max_tokens: int,
) -> JSONResponse:
    pieces: list[str] = []
    final: StreamChunk | None = None
    for chunk in engine.stream_generate(messages, max_tokens=max_tokens):
        if chunk.text:
            pieces.append(chunk.text)
        if chunk.is_final:
            final = chunk
    text = "".join(pieces)

    prompt_tokens = final.prompt_tokens if final else 0
    completion_tokens = final.generation_tokens if final else 0
    finish_reason = final.finish_reason if final else "stop"

    response = ChatCompletionResponse(
        id=_chat_id(),
        created=_now(),
        model=request_model or engine.model_id,
        choices=[
            Choice(
                index=0,
                message=ChoiceMessage(content=text),
                finish_reason=finish_reason,
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )
    return JSONResponse(response.model_dump())


def _streaming_response(
    engine: ServerEngine,
    request_model: str,
    messages: list[Message],
    max_tokens: int,
) -> StreamingResponse:
    response_id = _chat_id()
    created = _now()
    model_label = request_model or engine.model_id

    # Sync generator: Starlette will iterate in a threadpool, so blocking
    # engines (e.g. BatchingEngine waiting on a queue) do not stall the
    # event loop.
    def event_stream() -> Iterator[bytes]:
        # Opening chunk: assistant role.
        opening = ChatCompletionChunk(
            id=response_id,
            created=created,
            model=model_label,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChoiceDelta(role="assistant"),
                    finish_reason=None,
                )
            ],
        )
        yield _sse(opening.model_dump_json())

        final_chunk: StreamChunk | None = None
        for chunk in engine.stream_generate(messages, max_tokens=max_tokens):
            if chunk.is_final:
                final_chunk = chunk
                continue
            if not chunk.text:
                continue
            payload = ChatCompletionChunk(
                id=response_id,
                created=created,
                model=model_label,
                choices=[
                    ChunkChoice(
                        index=0,
                        delta=ChoiceDelta(content=chunk.text),
                        finish_reason=None,
                    )
                ],
            )
            yield _sse(payload.model_dump_json())

        finish_reason = (
            final_chunk.finish_reason if final_chunk is not None else "stop"
        )
        closing = ChatCompletionChunk(
            id=response_id,
            created=created,
            model=model_label,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChoiceDelta(),
                    finish_reason=finish_reason,
                )
            ],
        )
        yield _sse(closing.model_dump_json())
        yield b"data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(json_payload: str) -> bytes:
    return f"data: {json_payload}\n\n".encode()


# ─── Convenience runner (used by the CLI) ───────────────────────────


def run_server(
    model_id: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    log_level: str = "info",
) -> None:
    """Build the real engine, load it, and serve with uvicorn."""
    import uvicorn

    from vmlx.engine import SingleRequestEngine

    engine = SingleRequestEngine(model_id)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        engine.load()
        try:
            yield
        finally:
            engine.unload()

    app = create_app(engine)
    app.router.lifespan_context = lifespan
    uvicorn.run(app, host=host, port=port, log_level=log_level)
