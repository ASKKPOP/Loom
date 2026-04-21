"""End-to-end test: real MLX model + real HTTP server + official openai SDK client."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from openai import OpenAI

from vmlx.api.server import create_app
from vmlx.engine import SingleRequestEngine

TEST_MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def live_server() -> Iterator[tuple[str, SingleRequestEngine]]:
    """Boot a real uvicorn server in a background thread, yield the base URL."""
    engine = SingleRequestEngine(TEST_MODEL)
    engine.load()
    app = create_app(engine)

    port = _free_port()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the server to be ready (polling health endpoint).
    import urllib.request

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=0.5) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("uvicorn did not become ready in 10s")

    try:
        yield base_url, engine
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)
        engine.unload()


@pytest.mark.metal
def test_openai_sdk_list_models(
    live_server: tuple[str, SingleRequestEngine],
) -> None:
    base_url, engine = live_server
    client = OpenAI(base_url=f"{base_url}/v1", api_key="not-needed")
    models = client.models.list()
    ids = [m.id for m in models.data]
    assert engine.model_id in ids


@pytest.mark.metal
def test_openai_sdk_chat_completion_non_streaming(
    live_server: tuple[str, SingleRequestEngine],
) -> None:
    base_url, engine = live_server
    client = OpenAI(base_url=f"{base_url}/v1", api_key="not-needed")
    resp = client.chat.completions.create(
        model=engine.model_id,
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        max_tokens=20,
    )
    assert resp.id.startswith("chatcmpl-")
    assert resp.object == "chat.completion"
    assert len(resp.choices) == 1
    choice = resp.choices[0]
    assert choice.index == 0
    assert choice.message.role == "assistant"
    assert isinstance(choice.message.content, str) and choice.message.content
    assert resp.usage is not None
    assert resp.usage.completion_tokens > 0


@pytest.mark.metal
def test_openai_sdk_chat_completion_streaming(
    live_server: tuple[str, SingleRequestEngine],
) -> None:
    base_url, engine = live_server
    client = OpenAI(base_url=f"{base_url}/v1", api_key="not-needed")
    stream = client.chat.completions.create(
        model=engine.model_id,
        messages=[{"role": "user", "content": "Count: 1, 2, 3."}],
        max_tokens=20,
        stream=True,
    )
    chunks = list(stream)
    assert len(chunks) >= 2, "expected at least opening + closing chunks"

    # At least one chunk must carry role=assistant
    roles = [
        c.choices[0].delta.role for c in chunks if c.choices and c.choices[0].delta
    ]
    assert "assistant" in roles

    # Concatenated content should be non-empty
    content = "".join(
        (c.choices[0].delta.content or "")
        for c in chunks
        if c.choices and c.choices[0].delta and c.choices[0].delta.content
    )
    assert content, "expected some generated content across stream chunks"

    # Final chunk has a finish_reason
    finishes = [
        c.choices[0].finish_reason for c in chunks if c.choices[0].finish_reason
    ]
    assert finishes, "expected a finish_reason on the final chunk"
