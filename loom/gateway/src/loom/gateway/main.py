"""Loom API gateway.

Routes:
  GET  /health                 — liveness probe
  POST /v1/chat/completions    — proxied to the vMLX backend
  GET  /v1/models              — proxied to the vMLX backend

All other /v1/* paths are proxied transparently.

Environment variables:
  LOOM_BIND      — bind host (default: 127.0.0.1)
  LOOM_PORT      — bind port (default: 8080)
  LOOM_VMLX_URL  — vMLX backend base URL (default: http://127.0.0.1:8000)
  LOOM_LOG_LEVEL — log level (default: info)
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from loom.gateway import __version__
from loom.gateway import config as cfg
from loom.gateway.admin import router as admin_router
from loom.gateway.connectors import router as connectors_router
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

    app.include_router(admin_router)
    app.include_router(connectors_router)

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


# ─── Proxy helper ─────────────────────────────────────────────────────────────


async def _proxy(
    request: Request,
    path: str,
    client: httpx.AsyncClient,
) -> StreamingResponse | JSONResponse:
    body = await request.body()

    # Forward headers, minus hop-by-hop headers that httpx should not relay.
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
