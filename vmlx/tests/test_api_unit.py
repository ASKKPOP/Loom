"""Unit tests for the OpenAI-compatible API using FastAPI's TestClient + a stub engine."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from vmlx.api.server import create_app
from vmlx.engine import GenerationResult, Message, StreamChunk


class StubStreamEngine:
    """Stub engine supporting the server's ServerEngine protocol."""

    def __init__(
        self,
        model_id: str = "stub/chat",
        *,
        chunks: list[str] | None = None,
        finish_reason: str = "stop",
    ) -> None:
        self._model_id = model_id
        self._chunks = chunks or ["Hello", ", ", "world", "!"]
        self._finish_reason = finish_reason
        self.last_messages: list[Message] | str | None = None
        self.last_max_tokens: int | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def generate(
        self, prompt: str, *, max_tokens: int = 50
    ) -> GenerationResult:
        self.last_messages = prompt
        self.last_max_tokens = max_tokens
        text = "".join(self._chunks)
        return GenerationResult(
            text=text,
            prompt_tokens=5,
            generation_tokens=len(self._chunks),
            tokens_per_second=10.0,
            ttft_ms=50.0,
            peak_memory_mb=100.0,
            duration_s=0.5,
            finish_reason=self._finish_reason,
        )

    def stream_generate(
        self,
        messages: list[Message] | str,
        *,
        max_tokens: int = 50,
    ) -> Iterator[StreamChunk]:
        self.last_messages = messages
        self.last_max_tokens = max_tokens
        for c in self._chunks:
            yield StreamChunk(text=c, is_final=False, finish_reason=None)
        yield StreamChunk(
            text="",
            is_final=True,
            prompt_tokens=5,
            generation_tokens=len(self._chunks),
            tokens_per_second=10.0,
            peak_memory_mb=100.0,
            finish_reason=self._finish_reason,
        )


@pytest.fixture
def client() -> Iterator[tuple[TestClient, StubStreamEngine]]:
    engine = StubStreamEngine()
    app = create_app(engine)
    with TestClient(app) as c:
        yield c, engine


# ─── /health + /v1/models ───────────────────────────────────────────


def test_health(client: tuple[TestClient, StubStreamEngine]) -> None:
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_models_shows_loaded_model(
    client: tuple[TestClient, StubStreamEngine],
) -> None:
    c, engine = client
    r = c.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "list"
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == engine.model_id
    assert body["data"][0]["object"] == "model"


# ─── Non-streaming chat completion ──────────────────────────────────


def test_chat_completion_non_streaming_shape(
    client: tuple[TestClient, StubStreamEngine],
) -> None:
    c, _ = client
    r = c.post(
        "/v1/chat/completions",
        json={
            "model": "stub/chat",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 10,
            "stream": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "stub/chat"
    assert body["id"].startswith("chatcmpl-")
    assert isinstance(body["created"], int)
    assert len(body["choices"]) == 1
    choice = body["choices"][0]
    assert choice["index"] == 0
    assert choice["message"]["role"] == "assistant"
    assert choice["message"]["content"] == "Hello, world!"
    assert choice["finish_reason"] == "stop"
    assert body["usage"]["prompt_tokens"] == 5
    assert body["usage"]["completion_tokens"] == 4
    assert body["usage"]["total_tokens"] == 9


def test_chat_completion_passes_messages_to_engine(
    client: tuple[TestClient, StubStreamEngine],
) -> None:
    c, engine = client
    messages = [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ]
    r = c.post(
        "/v1/chat/completions",
        json={"model": "stub/chat", "messages": messages, "max_tokens": 10},
    )
    assert r.status_code == 200
    assert engine.last_messages == messages
    assert engine.last_max_tokens == 10


def test_chat_completion_rejects_n_not_1(
    client: tuple[TestClient, StubStreamEngine],
) -> None:
    c, _ = client
    r = c.post(
        "/v1/chat/completions",
        json={
            "model": "stub/chat",
            "messages": [{"role": "user", "content": "hi"}],
            "n": 2,
        },
    )
    assert r.status_code == 400
    assert "n=1" in r.json()["detail"]


def test_chat_completion_validates_empty_messages(
    client: tuple[TestClient, StubStreamEngine],
) -> None:
    c, _ = client
    r = c.post(
        "/v1/chat/completions",
        json={"model": "stub/chat", "messages": []},
    )
    assert r.status_code == 422  # pydantic validation


# ─── Streaming (SSE) chat completion ────────────────────────────────


def _parse_sse(body: str) -> list[dict[str, object] | str]:
    """Parse SSE `data: ...` lines into decoded payloads."""
    events: list[dict[str, object] | str] = []
    for raw in body.splitlines():
        if not raw.startswith("data: "):
            continue
        payload = raw[len("data: "):]
        if payload == "[DONE]":
            events.append("[DONE]")
        else:
            events.append(json.loads(payload))
    return events


def test_chat_completion_streaming_well_formed(
    client: tuple[TestClient, StubStreamEngine],
) -> None:
    c, _ = client
    with c.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "stub/chat",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 10,
            "stream": True,
        },
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes()).decode()
    events = _parse_sse(body)

    # Must end with [DONE]
    assert events[-1] == "[DONE]"
    # At least one opening (role delta), content deltas, and closing.
    assert len(events) >= 4  # role + >=1 content + closing + [DONE]

    chunk_events = [e for e in events[:-1] if isinstance(e, dict)]
    # Chunk object field must be chat.completion.chunk on every event.
    for e in chunk_events:
        assert e["object"] == "chat.completion.chunk"
        assert e["model"] == "stub/chat"
        assert isinstance(e["id"], str)
        assert len(e["choices"]) == 1

    # First chunk carries role="assistant"
    first = chunk_events[0]
    first_delta = first["choices"][0]["delta"]  # type: ignore[index]
    assert first_delta.get("role") == "assistant"

    # Concatenating content deltas reproduces the full text.
    content_pieces = []
    for e in chunk_events[1:-1]:
        delta = e["choices"][0]["delta"]  # type: ignore[index]
        if delta.get("content"):
            content_pieces.append(delta["content"])
    assert "".join(content_pieces) == "Hello, world!"

    # Last chunk before [DONE] has finish_reason.
    last = chunk_events[-1]
    assert last["choices"][0]["finish_reason"] == "stop"  # type: ignore[index]


def test_chat_completion_default_max_tokens_applied(
    client: tuple[TestClient, StubStreamEngine],
) -> None:
    """When request omits max_tokens, server uses default_max_tokens."""
    c, engine = client
    r = c.post(
        "/v1/chat/completions",
        json={
            "model": "stub/chat",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert r.status_code == 200
    assert engine.last_max_tokens == 512  # default in create_app


def test_custom_default_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = StubStreamEngine()
    app = create_app(engine, default_max_tokens=7)
    with TestClient(app) as c:
        c.post(
            "/v1/chat/completions",
            json={
                "model": "stub/chat",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert engine.last_max_tokens == 7


# ─── /admin/stats ───────────────────────────────────────────────────


def test_admin_stats_without_prefix_cache_reports_null(
    client: tuple[TestClient, StubStreamEngine],
) -> None:
    """When no PrefixCache is wired, the endpoint reports prefix_cache=null
    so consumers can tell caching isn't attached (vs. hit_rate=0.0 which
    would be ambiguous with 'attached but cold')."""
    c, engine = client
    r = c.get("/admin/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["vmlx_version"]
    assert body["model"] == engine.model_id
    assert body["prefix_cache"] is None


def test_admin_stats_reports_prefix_cache_hit_rate() -> None:
    """With a PrefixCache attached, /admin/stats returns real counters
    that reflect lookups/hits/misses so oncall can watch the hit rate."""
    from vmlx.cache import PagedCacheConfig, PagedKVCacheManager, PrefixCache

    cfg = PagedCacheConfig(
        num_blocks=8,
        num_layers=1,
        num_kv_heads=1,
        head_dim=4,
        block_size=4,
        dtype="float32",
    )
    m = PagedKVCacheManager(cfg)
    pc = PrefixCache(m)

    # Seed a prefix so we can record a hit.
    m.open_sequence("seed")
    import mlx.core as mx

    k = mx.zeros((4, 1, 4), dtype=mx.float32)
    v = mx.zeros((4, 1, 4), dtype=mx.float32)
    m.append_kv("seed", layer=0, k=k, v=v)
    blocks = m.block_table("seed")
    pc.insert([1, 2, 3, 4], blocks)

    # Exercise the cache: 1 hit, 1 miss.
    pc.lookup([1, 2, 3, 4])  # hit
    pc.lookup([9, 9, 9, 9])  # miss

    engine = StubStreamEngine()
    app = create_app(engine, prefix_cache=pc)
    with TestClient(app) as c:
        r = c.get("/admin/stats")
    assert r.status_code == 200
    body = r.json()
    pc_block = body["prefix_cache"]
    assert pc_block is not None
    assert pc_block["lookups"] == 2
    assert pc_block["hits"] == 1
    assert pc_block["misses"] == 1
    assert pc_block["hit_rate"] == pytest.approx(0.5)
    assert pc_block["cached_blocks"] == 1


# ─── _build_engine (run_server's engine factory) ────────────────────


def test_build_engine_defaults_to_batching() -> None:
    """The serving path defaults to BatchingEngine — continuous batching is
    vMLX's point over mlx-lm's single-request baseline."""
    from vmlx.api.server import _build_engine
    from vmlx.engine import BatchingEngine

    engine = _build_engine("mock/model", "batching", max_concurrent=16)
    assert isinstance(engine, BatchingEngine)
    assert engine.model_id == "mock/model"
    # max_concurrent is private but observable via constructor round-trip:
    assert engine._max_concurrent == 16  # type: ignore[attr-defined]


def test_build_engine_single_backward_compat() -> None:
    from vmlx.api.server import _build_engine
    from vmlx.engine import SingleRequestEngine

    engine = _build_engine("mock/model", "single", max_concurrent=32)
    assert isinstance(engine, SingleRequestEngine)
    assert engine.model_id == "mock/model"


def test_build_engine_rejects_unknown_type() -> None:
    from vmlx.api.server import _build_engine

    with pytest.raises(ValueError, match="unknown engine_type"):
        _build_engine("mock/model", "bogus", max_concurrent=1)
