"""Metal integration test for the benchmark harness — runs a real model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vmlx.benchmarks import run_benchmark
from vmlx.engine import SingleRequestEngine

TEST_MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"


@pytest.mark.metal
def test_benchmark_small_real_run(tmp_path: Path) -> None:
    """Run a tiny (n=3) real benchmark and verify the report & history file."""
    engine = SingleRequestEngine(TEST_MODEL)
    engine.load()
    try:
        report = run_benchmark(
            engine,
            engine_name="single",
            n=3,
            max_tokens=20,
            prompt="Count: 1, 2, 3.",
        )
    finally:
        engine.unload()

    # Required acceptance fields:
    assert report.ttft_p50_ms > 0.0
    assert report.ttft_p95_ms >= report.ttft_p50_ms
    assert report.tokens_per_sec > 0.0
    assert report.peak_rss_mb > 0.0
    assert report.total_duration_s > 0.0

    # Shape:
    assert report.engine == "single"
    assert report.model == TEST_MODEL
    assert report.n == 3
    assert len(report.per_request) == 3
    for r in report.per_request:
        assert r.ttft_ms > 0.0
        assert r.generation_tokens > 0

    # Append to a throwaway history file, ensure valid JSONL.
    history = tmp_path / "history.jsonl"
    report.append_to_history(str(history))
    lines = history.read_text().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["engine"] == "single"
    assert payload["model"] == TEST_MODEL
