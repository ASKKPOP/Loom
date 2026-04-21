"""Unit tests for BatchingEngine — no Metal / no model load.

The heavy, real-model tests live in ``test_engine_batching_metal.py``. Here
we verify construction, input validation, guard behavior, and the
benchmark runner's concurrent code path using a stub engine.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import pytest

from vmlx.benchmarks.registry import ENGINES, EngineProtocol, available_engines
from vmlx.benchmarks.runner import run_benchmark
from vmlx.engine import BatchingEngine, GenerationResult, Message, StreamChunk


def test_construct_without_load() -> None:
    e = BatchingEngine("some/model", max_concurrent=4)
    assert e.model_id == "some/model"
    assert e.is_loaded is False


def test_stream_generate_before_load_raises() -> None:
    e = BatchingEngine("some/model")
    with pytest.raises(RuntimeError, match="before load"):
        list(e.stream_generate("hi"))


def test_stream_generate_rejects_non_positive_max_tokens() -> None:
    e = BatchingEngine("some/model")
    with pytest.raises(ValueError, match="max_tokens must be positive"):
        list(e.stream_generate("hi", max_tokens=0))


def test_unload_is_safe_when_not_loaded() -> None:
    e = BatchingEngine("some/model")
    e.unload()  # must not raise
    assert e.is_loaded is False


def test_registry_exposes_batching() -> None:
    assert "batching" in available_engines()
    assert "single" in available_engines()


# ─── Concurrent benchmark runner (uses stub engine) ─────────────────


class SlowStubEngine:
    """Stub whose generate() sleeps briefly — lets us prove concurrency."""

    def __init__(self, model_id: str = "stub/concurrent", *, sleep_s: float = 0.05):
        self._model_id = model_id
        self._sleep_s = sleep_s
        self._lock = threading.Lock()
        self.active_peak = 0
        self._active = 0

    @property
    def model_id(self) -> str:
        return self._model_id

    def load(self) -> None:
        pass

    def unload(self) -> None:
        pass

    def generate(self, prompt: str, *, max_tokens: int = 50) -> GenerationResult:
        with self._lock:
            self._active += 1
            self.active_peak = max(self.active_peak, self._active)
        try:
            time.sleep(self._sleep_s)
            return GenerationResult(
                text="ok",
                prompt_tokens=3,
                generation_tokens=5,
                tokens_per_second=100.0,
                ttft_ms=10.0,
                peak_memory_mb=1.0,
                duration_s=self._sleep_s,
                finish_reason="length",
            )
        finally:
            with self._lock:
                self._active -= 1

    def stream_generate(
        self, messages: list[Message] | str, *, max_tokens: int = 50
    ) -> Iterator[StreamChunk]:
        r = self.generate(messages if isinstance(messages, str) else "stub")
        yield StreamChunk(text=r.text, is_final=False)
        yield StreamChunk(
            text="",
            is_final=True,
            prompt_tokens=r.prompt_tokens,
            generation_tokens=r.generation_tokens,
            tokens_per_second=r.tokens_per_second,
            ttft_ms=r.ttft_ms,
            peak_memory_mb=r.peak_memory_mb,
            finish_reason=r.finish_reason,
        )


def test_benchmark_runner_concurrent_actually_parallelizes() -> None:
    engine = SlowStubEngine(sleep_s=0.05)
    assert isinstance(engine, EngineProtocol)

    report = run_benchmark(
        engine,
        engine_name="stub",
        n=8,
        max_tokens=10,
        concurrent=8,
    )

    # If truly concurrent, peak active should be >1 (ideally 8).
    assert engine.active_peak >= 2, (
        f"expected parallel execution; peak concurrent calls was {engine.active_peak}"
    )
    # Total wall time should be much less than 8 * sleep_s (0.4s) — allow
    # generous slack for thread pool startup.
    assert report.total_duration_s < 0.35, (
        f"concurrent wall time too high: {report.total_duration_s:.3f}s "
        f"(expected < 0.35s for concurrent=8 with 0.05s per request)"
    )
    assert report.concurrent == 8
    assert report.n == 8
    assert len(report.per_request) == 8


def test_benchmark_runner_concurrent_equals_1_is_sequential() -> None:
    engine = SlowStubEngine(sleep_s=0.02)
    report = run_benchmark(
        engine, engine_name="stub", n=5, max_tokens=10, concurrent=1
    )
    assert engine.active_peak == 1
    assert report.concurrent == 1


def test_benchmark_runner_rejects_bad_concurrent() -> None:
    engine = SlowStubEngine()
    with pytest.raises(ValueError, match="concurrent must be positive"):
        run_benchmark(engine, engine_name="stub", n=1, max_tokens=5, concurrent=0)


def test_batching_in_registry_builds_engine() -> None:
    factory = ENGINES["batching"]
    engine = factory("mx/some-model")
    assert engine.model_id == "mx/some-model"
    assert engine.is_loaded is False
