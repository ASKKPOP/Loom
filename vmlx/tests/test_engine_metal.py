"""Metal integration tests — run a real model on Apple Silicon.

These tests are marked `@pytest.mark.metal` so they can be skipped on CI
machines without Metal. Locally on an M-series Mac they should complete in
well under a minute on the first run (model download) and seconds on repeat.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from vmlx.engine import SingleRequestEngine

TEST_MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"


@pytest.fixture(scope="module")
def engine() -> Iterator[SingleRequestEngine]:
    e = SingleRequestEngine(TEST_MODEL)
    e.load()
    try:
        yield e
    finally:
        e.unload()


@pytest.mark.metal
def test_load_and_generate_50_tokens(engine: SingleRequestEngine) -> None:
    result = engine.generate(
        "Write the number 1 then the number 2 then the number 3.",
        max_tokens=50,
    )
    assert result.text, "expected non-empty generated text"
    assert result.prompt_tokens > 0
    # Model may stop early via EOS; accept anything in [1, 50].
    assert 1 <= result.generation_tokens <= 50
    assert result.tokens_per_second > 0.0
    assert result.peak_memory_mb > 0.0
    assert result.duration_s > 0.0


@pytest.mark.metal
def test_ten_sequential_generations_no_unbounded_memory_growth(
    engine: SingleRequestEngine,
) -> None:
    """Peak memory should stabilize after warmup — not grow every iteration.

    Qwen2.5-0.5B-4bit lives in ~400MB. Any leak that added even a few MB per
    call would show up dramatically over 10 iterations.
    """
    peaks: list[float] = []
    for i in range(10):
        result = engine.generate(f"Count to three. Iteration {i}.", max_tokens=20)
        assert result.generation_tokens > 0
        peaks.append(result.peak_memory_mb)

    first_peak = peaks[0]
    max_peak = max(peaks)
    # Allow generous slack for allocator behavior, but reject unbounded growth:
    # peak after 10 runs must not be more than 2x the first run's peak.
    assert max_peak <= first_peak * 2.0, (
        f"peak memory grew unboundedly across 10 generations: "
        f"first={first_peak:.1f}MB max={max_peak:.1f}MB peaks={peaks}"
    )


@pytest.mark.metal
def test_generate_before_load_raises_on_real_engine() -> None:
    # Fresh engine, not loaded: must raise without any Metal allocation.
    fresh = SingleRequestEngine(TEST_MODEL)
    with pytest.raises(RuntimeError, match="before load"):
        fresh.generate("hi")
