"""Unit tests for the benchmark harness — no Metal required.

Uses a stub engine so we can verify percentile math, report shape, registry
behavior, and CLI wiring without loading a real model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vmlx.benchmarks import run_benchmark
from vmlx.benchmarks.registry import (
    ENGINES,
    EngineProtocol,
    available_engines,
    build_engine,
)
from vmlx.benchmarks.report import BenchmarkReport, RequestMetrics
from vmlx.benchmarks.run import build_parser
from vmlx.benchmarks.run import main as run_main
from vmlx.benchmarks.runner import _percentile
from vmlx.engine import GenerationResult


class StubEngine:
    """Deterministic engine that records calls and returns canned results."""

    def __init__(
        self,
        model_id: str,
        *,
        ttfts_ms: list[float] | None = None,
        gen_tokens: int = 50,
        tps: float = 25.0,
        duration_s: float = 2.0,
        peak_mb: float = 512.0,
    ) -> None:
        self._model_id = model_id
        self._loaded = False
        self._ttfts = ttfts_ms or [50.0]
        self._call_index = 0
        self._gen_tokens = gen_tokens
        self._tps = tps
        self._duration_s = duration_s
        self._peak_mb = peak_mb
        self.calls: list[tuple[str, int]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def generate(self, prompt: str, *, max_tokens: int = 50) -> GenerationResult:
        if not self._loaded:
            raise RuntimeError("stub engine not loaded")
        self.calls.append((prompt, max_tokens))
        ttft = self._ttfts[self._call_index % len(self._ttfts)]
        self._call_index += 1
        return GenerationResult(
            text="stub output",
            prompt_tokens=10,
            generation_tokens=self._gen_tokens,
            tokens_per_second=self._tps,
            ttft_ms=ttft,
            peak_memory_mb=self._peak_mb,
            duration_s=self._duration_s,
            finish_reason="length",
        )


# ─────────────────── registry ───────────────────────────────────────


def test_registry_has_single_engine() -> None:
    assert "single" in available_engines()


def test_build_engine_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unknown engine"):
        build_engine("does-not-exist", "some/model")


def test_stub_engine_conforms_to_protocol() -> None:
    # runtime_checkable Protocol — verify our stub satisfies it.
    stub = StubEngine("some/model")
    assert isinstance(stub, EngineProtocol)


# ─────────────────── percentiles ────────────────────────────────────


def test_percentile_empty() -> None:
    assert _percentile([], 50.0) == 0.0


def test_percentile_single() -> None:
    assert _percentile([42.0], 50.0) == 42.0
    assert _percentile([42.0], 95.0) == 42.0


def test_percentile_sorted_midpoint() -> None:
    # p50 of [10, 20, 30, 40, 50] → 30.0
    assert _percentile([10.0, 20.0, 30.0, 40.0, 50.0], 50.0) == pytest.approx(30.0)


def test_percentile_p95_interpolation() -> None:
    # p95 of 20 values [1..20]: k = 19 * 0.95 = 18.05
    # → 0.95 * 19 + 0.05 * 20 = 18.05 + 1.0 = 19.05
    values = [float(i) for i in range(1, 21)]
    assert _percentile(values, 95.0) == pytest.approx(19.05)


# ─────────────────── run_benchmark ──────────────────────────────────


def test_run_benchmark_produces_report_shape() -> None:
    engine = StubEngine(
        "some/model",
        ttfts_ms=[100.0, 120.0, 80.0, 150.0, 90.0],
        gen_tokens=50,
    )
    engine.load()

    report = run_benchmark(
        engine,
        engine_name="stub",
        n=5,
        max_tokens=50,
        prompt="hello",
    )

    assert isinstance(report, BenchmarkReport)
    assert report.engine == "stub"
    assert report.model == "some/model"
    assert report.n == 5
    assert report.max_tokens == 50
    assert report.prompt_chars == len("hello")
    assert len(report.per_request) == 5
    # Required metrics from acceptance criteria:
    assert report.ttft_p50_ms > 0.0
    assert report.ttft_p95_ms >= report.ttft_p50_ms
    assert report.tokens_per_sec > 0.0
    assert report.peak_rss_mb > 0.0
    assert report.total_duration_s > 0.0
    # Environment capture:
    assert report.vmlx_version
    assert report.python_version
    assert report.platform


def test_run_benchmark_records_each_call() -> None:
    engine = StubEngine("some/model")
    engine.load()
    report = run_benchmark(
        engine, engine_name="stub", n=3, max_tokens=20, prompt="hi"
    )
    assert engine.calls == [("hi", 20), ("hi", 20), ("hi", 20)]
    assert [r.i for r in report.per_request] == [0, 1, 2]


def test_run_benchmark_rejects_bad_n() -> None:
    engine = StubEngine("some/model")
    engine.load()
    with pytest.raises(ValueError, match="n must be positive"):
        run_benchmark(engine, engine_name="stub", n=0, max_tokens=10)


def test_run_benchmark_rejects_bad_max_tokens() -> None:
    engine = StubEngine("some/model")
    engine.load()
    with pytest.raises(ValueError, match="max_tokens must be positive"):
        run_benchmark(engine, engine_name="stub", n=1, max_tokens=0)


# ─────────────────── report serialization ───────────────────────────


def test_report_to_json_roundtrip() -> None:
    engine = StubEngine("some/model")
    engine.load()
    report = run_benchmark(engine, engine_name="stub", n=2, max_tokens=5)
    payload = json.loads(report.to_json())
    assert payload["engine"] == "stub"
    assert payload["model"] == "some/model"
    assert payload["n"] == 2
    assert len(payload["per_request"]) == 2
    assert "ttft_p50_ms" in payload
    assert "ttft_p95_ms" in payload
    assert "tokens_per_sec" in payload
    assert "peak_rss_mb" in payload
    assert "total_duration_s" in payload


def test_history_append_creates_jsonl(tmp_path: Path) -> None:
    engine = StubEngine("some/model")
    engine.load()
    r1 = run_benchmark(engine, engine_name="stub", n=2, max_tokens=5)
    r2 = run_benchmark(engine, engine_name="stub", n=2, max_tokens=5)
    history = tmp_path / "history.jsonl"
    r1.append_to_history(str(history))
    r2.append_to_history(str(history))

    lines = history.read_text().splitlines()
    assert len(lines) == 2
    p1 = json.loads(lines[0])
    p2 = json.loads(lines[1])
    assert p1["engine"] == "stub"
    assert p2["engine"] == "stub"


def test_request_metrics_is_frozen() -> None:
    m = RequestMetrics(
        i=0, ttft_ms=10.0, generation_tokens=5,
        tokens_per_second=1.0, duration_s=0.1, peak_memory_mb=1.0,
        finish_reason="stop",
    )
    with pytest.raises(Exception):  # noqa: B017 — FrozenInstanceError is a subclass
        m.i = 99  # type: ignore[misc]


# ─────────────────── CLI wiring ─────────────────────────────────────


def test_cli_parser_required_args() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["--engine", "single", "--model", "mx/m", "--n", "3"]
    )
    assert args.engine == "single"
    assert args.model == "mx/m"
    assert args.n == 3
    assert args.max_tokens == 100  # default


def test_cli_parser_rejects_unknown_engine() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["--engine", "bogus", "--model", "mx/m", "--n", "3"]
        )


def test_cli_main_with_stub_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Swap the "single" engine factory for our stub so the CLI can run
    # end-to-end without Metal.
    monkeypatch.setitem(ENGINES, "single", lambda model_id: StubEngine(model_id))
    output = tmp_path / "report.json"
    history = tmp_path / "history.jsonl"

    rc = run_main(
        [
            "--engine", "single",
            "--model", "stub/model",
            "--n", "3",
            "--max-tokens", "10",
            "--output", str(output),
            "--history", str(history),
        ]
    )

    assert rc == 0
    assert output.exists()
    payload = json.loads(output.read_text())
    assert payload["engine"] == "single"
    assert payload["model"] == "stub/model"
    assert payload["n"] == 3
    assert history.exists()
    history_lines = history.read_text().splitlines()
    assert len(history_lines) == 1


def test_cli_main_no_history_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(ENGINES, "single", lambda model_id: StubEngine(model_id))
    output = tmp_path / "report.json"
    history = tmp_path / "no_such_history.jsonl"
    rc = run_main(
        [
            "--engine", "single",
            "--model", "stub/model",
            "--n", "2",
            "--max-tokens", "5",
            "--output", str(output),
            "--history", str(history),
            "--no-history",
        ]
    )
    assert rc == 0
    assert output.exists()
    assert not history.exists(), "history file should not be created with --no-history"
