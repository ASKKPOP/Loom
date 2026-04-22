"""Unit tests for the Loom gateway.

The vMLX backend is mocked with respx + a fake httpx.AsyncClient so tests
run without a live vMLX instance. The TestClient context manager triggers
the FastAPI lifespan.
"""

from __future__ import annotations

import json
from collections.abc import Generator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from loom.gateway.main import create_app

FAKE_BACKEND = "http://fake-vmlx"


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_client() -> Generator[httpx.AsyncClient, None, None]:
    """An httpx.AsyncClient whose transport is intercepted by respx."""
    with respx.MockRouter(base_url=FAKE_BACKEND, assert_all_called=False) as router:
        transport = httpx.MockTransport(router.handler)  # type: ignore[arg-type]
        client = httpx.AsyncClient(
            base_url=FAKE_BACKEND,
            transport=transport,
        )
        yield client


@pytest.fixture()
def client(mock_client: httpx.AsyncClient) -> Generator[TestClient, None, None]:
    app = create_app(backend_url=FAKE_BACKEND, http_client=mock_client)
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ─── /health ──────────────────────────────────────────────────────────────────


def test_health_returns_200() -> None:
    app = create_app(backend_url=FAKE_BACKEND)
    with TestClient(app) as c:
        resp = c.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


# ─── CORS headers ─────────────────────────────────────────────────────────────


def test_cors_headers_present_on_health() -> None:
    app = create_app(backend_url=FAKE_BACKEND)
    with TestClient(app) as c:
        resp = c.get("/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_cors_preflight() -> None:
    app = create_app(backend_url=FAKE_BACKEND)
    with TestClient(app) as c:
        resp = c.options(
            "/v1/chat/completions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "*"


# ─── /v1/chat/completions non-streaming ───────────────────────────────────────


def test_non_streaming_proxied_to_backend(
    client: TestClient, mock_client: httpx.AsyncClient
) -> None:
    payload = {
        "id": "chatcmpl-abc",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }

    with respx.mock(base_url=FAKE_BACKEND) as router:
        router.post("/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=payload)
        )
        # Re-attach mock transport to the injected client.
        mock_client._transport = httpx.MockTransport(router.handler)  # type: ignore[assignment]

        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "Hello!"


def test_backend_error_status_propagated(
    client: TestClient, mock_client: httpx.AsyncClient
) -> None:
    with respx.mock(base_url=FAKE_BACKEND) as router:
        router.post("/v1/chat/completions").mock(
            return_value=httpx.Response(
                503,
                json={"error": {"message": "service unavailable", "type": "server_error"}},
            )
        )
        mock_client._transport = httpx.MockTransport(router.handler)  # type: ignore[assignment]

        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )

    assert resp.status_code == 503


# ─── /v1/chat/completions streaming ──────────────────────────────────────────


def test_streaming_sse_proxied(
    client: TestClient, mock_client: httpx.AsyncClient
) -> None:
    sse_body = (
        b'data: {"id":"c1","object":"chat.completion.chunk","created":1,"model":"m",'
        b'"choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n'
        b'data: {"id":"c1","object":"chat.completion.chunk","created":1,"model":"m",'
        b'"choices":[{"index":0,"delta":{"content":"Hi"},"finish_reason":null}]}\n\n'
        b"data: [DONE]\n\n"
    )

    with respx.mock(base_url=FAKE_BACKEND) as router:
        router.post("/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                content=sse_body,
                headers={"content-type": "text/event-stream"},
            )
        )
        mock_client._transport = httpx.MockTransport(router.handler)  # type: ignore[assignment]

        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            raw = resp.read().decode()

    assert "[DONE]" in raw
    assert "Hi" in raw


# ─── /v1/models ───────────────────────────────────────────────────────────────


def test_models_proxied(
    client: TestClient, mock_client: httpx.AsyncClient
) -> None:
    with respx.mock(base_url=FAKE_BACKEND) as router:
        router.get("/v1/models").mock(
            return_value=httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [
                        {"id": "my-model", "object": "model", "created": 0, "owned_by": "local"}
                    ],
                },
            )
        )
        mock_client._transport = httpx.MockTransport(router.handler)  # type: ignore[assignment]

        resp = client.get("/v1/models")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data[0]["id"] == "my-model"


# ─── Config / env binding ─────────────────────────────────────────────────────


def test_default_backend_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOM_VMLX_URL", "http://custom-backend:9999")
    from loom.gateway import config as cfg

    assert cfg.vmlx_url() == "http://custom-backend:9999"


def test_bind_host_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOOM_BIND", raising=False)
    from loom.gateway import config as cfg

    assert cfg.bind_host() == "127.0.0.1"


def test_bind_host_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOM_BIND", "0.0.0.0")
    from loom.gateway import config as cfg

    assert cfg.bind_host() == "0.0.0.0"


# ─── Structured logging smoke ─────────────────────────────────────────────────


def test_json_log_format() -> None:
    import logging

    from loom.gateway.logging_setup import _JsonFormatter

    fmt = _JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    line = fmt.format(record)
    parsed = json.loads(line)
    assert parsed["level"] == "INFO"
    assert parsed["msg"] == "hello world"
    assert "ts" in parsed
