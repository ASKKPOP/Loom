"""Metal integration tests for BatchingEngine.

These load a real (small) MLX model and exercise continuous batching at
concurrency. They cover the vmlx-005 acceptance criteria:

- Throughput: N=8 concurrent requests serves ≥ 3× req/s vs single-request
- TTFT: median TTFT does not regress > 20% vs single-request
- Correctness: under greedy sampling, batched output equals single output
  for the same prompt
- Stress: 100 requests, bounded wall-clock, no deadlocks, no drops
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import median

import pytest

from vmlx.engine import BatchingEngine, SingleRequestEngine

TEST_MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"
PROMPT = "Write exactly three short bullet points about the number seven."


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def batching_engine() -> Iterator[BatchingEngine]:
    e = BatchingEngine(TEST_MODEL, max_concurrent=8)
    e.load()
    try:
        yield e
    finally:
        e.unload()


@pytest.fixture(scope="module")
def single_engine() -> Iterator[SingleRequestEngine]:
    e = SingleRequestEngine(TEST_MODEL)
    e.load()
    try:
        yield e
    finally:
        e.unload()


# ─── Basic smoke ────────────────────────────────────────────────────


@pytest.mark.metal
def test_single_request_through_batching_engine(
    batching_engine: BatchingEngine,
) -> None:
    r = batching_engine.generate("Reply with: OK", max_tokens=10)
    assert r.text
    assert r.generation_tokens > 0
    assert r.ttft_ms > 0.0
    assert r.finish_reason in {"length", "stop"}


# ─── Correctness: same prompt, greedy → byte-identical output ───────


@pytest.mark.metal
def test_batched_output_matches_single_for_greedy_sampling(
    batching_engine: BatchingEngine,
    single_engine: SingleRequestEngine,
) -> None:
    """With the default argmax (greedy) sampler, batched and single-request
    generation must produce the same tokens for the same prompt.

    We compare text (not token ids) because BatchGenerator's tokenizer-end
    handling may omit EOS while SingleRequestEngine includes it, but the
    visible output text should match.
    """
    max_tokens = 30
    single_result = single_engine.generate(PROMPT, max_tokens=max_tokens)

    # Submit the same prompt 8× concurrently on the batching engine.
    def one() -> str:
        return batching_engine.generate(PROMPT, max_tokens=max_tokens).text

    with ThreadPoolExecutor(max_workers=8) as ex:
        outputs = [f.result() for f in [ex.submit(one) for _ in range(8)]]

    # All 8 batched outputs must agree with each other …
    assert len(set(outputs)) == 1, (
        "batched outputs diverged across concurrent requests: "
        f"unique_count={len(set(outputs))}"
    )
    # … and agree with the single-request baseline.
    assert outputs[0] == single_result.text, (
        "batched output does not match single-request output under greedy "
        f"sampling.\nsingle  : {single_result.text!r}\nbatched : {outputs[0]!r}"
    )


# ─── Throughput + TTFT acceptance gates ─────────────────────────────


@pytest.mark.metal
def test_throughput_gate_8_concurrent(
    batching_engine: BatchingEngine,
    single_engine: SingleRequestEngine,
) -> None:
    """vmlx-005 acceptance: N=8 concurrent must serve ≥ 3× req/s vs single."""
    max_tokens = 30
    n = 8

    # Baseline: 8 requests, sequential, via SingleRequestEngine.
    t0 = time.perf_counter()
    for _ in range(n):
        single_engine.generate(PROMPT, max_tokens=max_tokens)
    single_wall = time.perf_counter() - t0
    single_rps = n / single_wall

    # Batching: 8 requests, concurrent, via BatchingEngine.
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n) as ex:
        futures = [
            ex.submit(batching_engine.generate, PROMPT, max_tokens=max_tokens)
            for _ in range(n)
        ]
        for f in as_completed(futures):
            f.result()
    batch_wall = time.perf_counter() - t0
    batch_rps = n / batch_wall

    ratio = batch_rps / single_rps
    print(
        f"\nthroughput: single={single_rps:.2f} req/s  "
        f"batching={batch_rps:.2f} req/s  ratio={ratio:.2f}x"
    )
    assert ratio >= 3.0, (
        f"vmlx-005 gate: batched req/s must be ≥ 3× single ({ratio:.2f}×)"
    )


@pytest.mark.metal
def test_median_ttft_no_regression(
    batching_engine: BatchingEngine,
    single_engine: SingleRequestEngine,
) -> None:
    """Median TTFT under concurrency must not be > 20% worse than single."""
    max_tokens = 15

    # Baseline single: a few runs to get a stable median.
    single_ttfts: list[float] = []
    for _ in range(4):
        r = single_engine.generate(PROMPT, max_tokens=max_tokens)
        single_ttfts.append(r.ttft_ms)
    single_median = median(single_ttfts)

    # Concurrent under BatchingEngine.
    def one() -> float:
        return batching_engine.generate(PROMPT, max_tokens=max_tokens).ttft_ms

    with ThreadPoolExecutor(max_workers=8) as ex:
        batch_ttfts = [f.result() for f in [ex.submit(one) for _ in range(8)]]
    batch_median = median(batch_ttfts)

    ratio = batch_median / single_median if single_median > 0 else float("inf")
    print(
        f"\nmedian TTFT: single={single_median:.1f}ms  "
        f"batching={batch_median:.1f}ms  ratio={ratio:.2f}x"
    )
    assert batch_median <= single_median * 1.20, (
        f"median TTFT regressed by more than 20%: "
        f"single={single_median:.1f}ms, batched={batch_median:.1f}ms"
    )


# ─── Stress ─────────────────────────────────────────────────────────


@pytest.mark.metal
def test_stress_100_requests_no_drops_no_deadlocks(
    batching_engine: BatchingEngine,
) -> None:
    """Submit 100 requests, verify all complete within a generous budget."""
    n = 100
    max_tokens = 10
    completed = threading.Event()
    counter = {"n": 0}
    lock = threading.Lock()

    def one() -> None:
        r = batching_engine.generate("Say: OK", max_tokens=max_tokens)
        assert r.generation_tokens > 0
        with lock:
            counter["n"] += 1
            if counter["n"] == n:
                completed.set()

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(one) for _ in range(n)]
        # Wait for all to finish, bounded by acceptance gate (30s).
        done = completed.wait(timeout=30.0)
        # Collect exceptions too.
        for f in futures:
            f.result(timeout=5.0)
    wall = time.perf_counter() - start

    assert done, f"stress test timed out after 30s with only {counter['n']}/{n} completed"
    assert counter["n"] == n, f"dropped requests: completed={counter['n']}/{n}"
    assert wall <= 30.0
    print(f"\nstress: {n} requests completed in {wall:.1f}s")
