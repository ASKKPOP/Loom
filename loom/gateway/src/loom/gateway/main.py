"""Loom API gateway.

Routes:
  GET  /health                 — liveness probe
  POST /v1/chat/completions    — proxied to the vMLX backend
  GET  /v1/models              — proxied to the vMLX backend

All other /v1/* paths are proxied transparently.

Environment variables:
  LOOM_BIND            — bind host (default: 127.0.0.1)
  LOOM_PORT            — bind port (default: 8080)
  LOOM_VMLX_URL        — vMLX backend base URL (default: http://127.0.0.1:8000)
  LOOM_LOG_LEVEL       — log level (default: info)
  LOOM_INJECT_CONTEXT  — inject date/capability preamble into chat requests (default: true)
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import AsyncIterator
from datetime import date

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from loom.gateway import __version__
from loom.gateway import config as cfg
from loom.gateway.logging_setup import configure as configure_logging

log = logging.getLogger(__name__)

# ─── App factory ──────────────────────────────────────────────────────────────


def create_app(
    backend_url: str | None = None,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> FastAPI:
    """Build and return the gateway FastAPI app.

    ``backend_url`` overrides ``LOOM_VMLX_URL``.
    ``http_client`` injects a pre-built client (used in tests to inject mocked
    transport); when omitted a real client is created in the lifespan.
    """
    resolved_backend = (backend_url or cfg.vmlx_url()).rstrip("/")

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(cfg.log_level())
        log.info("Loom gateway starting", extra={"backend": resolved_backend})
        if http_client is not None:
            app.state.backend = http_client
            yield
        else:
            async with httpx.AsyncClient(
                base_url=resolved_backend,
                timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0),
            ) as client:
                app.state.backend = client
                yield
        log.info("Loom gateway stopped")

    app = FastAPI(
        title="Loom Gateway",
        version=__version__,
        description="Local AI gateway — proxies OpenAI-compatible requests to vMLX.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health ──────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    # ── Proxy /v1/* to vMLX ─────────────────────────────────────────────────

    @app.api_route(
        "/v1/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        response_model=None,
    )
    async def proxy_v1(path: str, request: Request) -> StreamingResponse | JSONResponse:
        return await _proxy(request, f"/v1/{path}", app.state.backend)

    return app


# ─── Context injection ────────────────────────────────────────────────────────

# Tells the model what it does and does not have access to in this deployment.
# Updated to the current date at request time so the model never claims to be
# in its training-cutoff year.
_CONTEXT_TEMPLATE = (
    "The current date is {today}. You are a locally hosted assistant running "
    "on the user's own hardware via the Loom platform.\n\n"
    "You do not have built-in internet access, web search, or tools for fetching "
    "live data in this deployment. If the user asks about current events, prices, "
    "schedules, weather, news, or anything time-sensitive beyond your training data, "
    "do not guess. Say plainly that you cannot fetch live information from this "
    "deployment, and ask the user to paste the relevant text, URL contents, or data "
    "so you can reason over it."
)


def _build_context_preamble(today: date | None = None) -> str:
    return _CONTEXT_TEMPLATE.format(today=(today or date.today()).isoformat())


def _inject_chat_context(body: bytes, *, today: date | None = None) -> bytes:
    """Prepend a date/capability preamble to a chat-completions request body.

    On any parse failure the body is returned unchanged — we never want context
    injection to break an otherwise valid proxy call.
    """
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return body

    if not isinstance(payload, dict):
        return body
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return body

    preamble = _build_context_preamble(today)

    if messages and isinstance(messages[0], dict) and messages[0].get("role") == "system":
        existing = messages[0].get("content")
        if isinstance(existing, str) and existing.strip():
            messages[0]["content"] = f"{preamble}\n\n{existing}"
        else:
            messages[0]["content"] = preamble
    else:
        messages.insert(0, {"role": "system", "content": preamble})

    payload["messages"] = messages
    return json.dumps(payload).encode("utf-8")


# ─── Proxy helper ─────────────────────────────────────────────────────────────


async def _proxy(
    request: Request,
    path: str,
    client: httpx.AsyncClient,
) -> StreamingResponse | JSONResponse:
    body = await request.body()

    if (
        request.method == "POST"
        and path == "/v1/chat/completions"
        and cfg.inject_context()
    ):
        body = _inject_chat_context(body)

    # Forward headers, minus hop-by-hop headers that httpx should not relay.
    # Content-Length is dropped so httpx recomputes it after any body rewrite.
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower()
        not in {
            "host",
            "content-length",
            "transfer-encoding",
            "connection",
            "keep-alive",
            "upgrade",
        }
    }

    log.debug("proxy → %s %s", request.method, path)

    upstream = client.build_request(
        method=request.method,
        url=path,
        headers=headers,
        params=dict(request.query_params),
        content=body,
    )

    response = await client.send(upstream, stream=True)

    content_type = response.headers.get("content-type", "")
    is_sse = "text/event-stream" in content_type

    if is_sse:
        return StreamingResponse(
            response.aiter_bytes(),
            status_code=response.status_code,
            headers=_safe_headers(response.headers),
            media_type="text/event-stream",
        )

    content = await response.aread()
    await response.aclose()

    log.debug(
        "proxy ← %s %s %d",
        request.method,
        path,
        response.status_code,
    )

    return JSONResponse(
        content=_decode_json(content),
        status_code=response.status_code,
        headers=_safe_headers(response.headers),
    )


def _safe_headers(headers: httpx.Headers) -> dict[str, str]:
    skip = {
        "content-encoding",
        "transfer-encoding",
        "connection",
        "content-length",
    }
    return {k: v for k, v in headers.items() if k.lower() not in skip}


def _decode_json(content: bytes) -> object:
    import json

    try:
        return json.loads(content)
    except Exception:
        return content.decode("utf-8", errors="replace")


# ─── CLI entry-point ──────────────────────────────────────────────────────────


def run_gateway_cli() -> None:  # pragma: no cover
    import uvicorn

    configure_logging(cfg.log_level())
    app = create_app()
    uvicorn.run(
        app,
        host=cfg.bind_host(),
        port=cfg.bind_port(),
        log_level=cfg.log_level(),
        log_config=None,  # use our own JSON logger
    )


# Allow `uvicorn loom.gateway.main:app` usage (reads env at import time).
app = create_app()
