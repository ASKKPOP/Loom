"""Unit tests for the vmlx-vs-mlx-lm comparison harness.

Exercises the parts that don't need real servers: CLI parsing, concurrency
sweep with a stubbed request function, markdown emission, and commentary
generation. The actual head-to-head run is exercised under @metal in a
separate file to keep this suite fast.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

import pytest

from vmlx.benchmarks.compare_mlx_lm import (
    BenchmarkRun,
    LevelResult,
    RequestSample,
    _build_shared_prefix,
    _fmt_ratio,
    _format_markdown,
    _parse_concurrency,
    _percentile,
    _render_caveats,
    _render_commentary,
    _render_ratios_table,
    _render_results_table,
    _run_level,
    _safe_ratio,
    _vmlx_server_spec,
    build_parser,
)

# ─── CLI parsing ───────────────────────────────────────────────────────


def test_parse_concurrency_basic() -> None:
    assert _parse_concurrency("1,4,8,16") == [1, 4, 8, 16]


def test_parse_concurrency_tolerates_whitespace() -> None:
    assert _parse_concurrency(" 1 ,  4,8 ") == [1, 4, 8]


def test_parse_concurrency_rejects_zero() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_concurrency("1,0,4")


def test_parse_concurrency_rejects_negative() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_concurrency("-1,4")


def test_parse_concurrency_rejects_empty() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_concurrency("")


def test_build_parser_defaults() -> None:
    p = build_parser()
    args = p.parse_args(["--model", "mock/model"])
    assert args.model == "mock/model"
    assert args.concurrency == [1, 4, 8, 16]
    assert args.requests_per_level == 8
    assert args.max_tokens == 64
    assert args.shared_prefix_chars == 1200
    assert args.output == Path("docs/vmlx/benchmarks/vs-mlx-lm.md")
    assert args.skip_vmlx is False
    assert args.skip_mlx_lm is False


def test_build_parser_accepts_custom_concurrency() -> None:
    p = build_parser()
    args = p.parse_args(["--model", "m", "--concurrency", "2,8"])
    assert args.concurrency == [2, 8]


# ─── Shared prefix construction ────────────────────────────────────────


def test_build_shared_prefix_pads_to_target() -> None:
    prefix = _build_shared_prefix(1500)
    # Allow a little undershoot because padding happens in filler chunks
    # and we stop as soon as we reach target_chars.
    assert 1499 <= len(prefix) <= 1505


def test_build_shared_prefix_returns_base_when_shorter_target() -> None:
    # The base prompt is already ~900 chars; target=100 should just return
    # the base unchanged rather than truncate (safer).
    prefix = _build_shared_prefix(100)
    assert "careful, concise assistant" in prefix


# ─── Percentile ────────────────────────────────────────────────────────


def test_percentile_empty_is_zero() -> None:
    assert _percentile([], 50.0) == 0.0


def test_percentile_singleton_returns_value() -> None:
    assert _percentile([42.0], 95.0) == 42.0


def test_percentile_linear_interpolation() -> None:
    # p50 of [1..5] is 3.0 under linear interpolation.
    assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50.0) == 3.0


def test_percentile_p95_of_four() -> None:
    # p95 of [1,2,3,4]: k = 3 * 0.95 = 2.85 → lerp between idx 2 (3) and 3 (4)
    result = _percentile([1.0, 2.0, 3.0, 4.0], 95.0)
    assert result == pytest.approx(3.85)


# ─── Ratio helpers ─────────────────────────────────────────────────────


def test_safe_ratio_zero_denom() -> None:
    assert _safe_ratio(1.0, 0.0) is None


def test_safe_ratio_normal() -> None:
    assert _safe_ratio(4.0, 2.0) == 2.0


def test_fmt_ratio_none() -> None:
    assert _fmt_ratio(None) == "n/a"


def test_fmt_ratio_numeric() -> None:
    assert _fmt_ratio(1.234) == "1.23×"


# ─── _run_level with stubbed request function ──────────────────────────


def test_run_level_aggregates_samples() -> None:
    """With a deterministic stub request fn we can verify aggregation math
    without standing up a server."""
    samples = [
        RequestSample(ttft_ms=100.0, duration_s=1.0, generation_tokens=50, ok=True),
        RequestSample(ttft_ms=120.0, duration_s=1.1, generation_tokens=55, ok=True),
        RequestSample(ttft_ms=0.0, duration_s=0.5, generation_tokens=0, ok=False, error="boom"),
        RequestSample(ttft_ms=150.0, duration_s=1.2, generation_tokens=60, ok=True),
    ]
    it = iter(samples)

    def stub(
        base_url: str,
        model: str,
        system: str,
        user: str,
        *,
        max_tokens: int,
    ) -> RequestSample:
        return next(it)

    result = _run_level(
        base_url="http://stub",
        model="mock/model",
        concurrency=2,
        n_requests=4,
        shared_prefix="sys",
        suffixes=["u1", "u2", "u3", "u4"],
        max_tokens=16,
        rss_sampler=None,
        server_name="vmlx",
        request_fn=stub,
    )

    assert result.server == "vmlx"
    assert result.concurrency == 2
    assert result.n_requests == 4
    assert result.ok_count == 3
    # TTFTs from the 3 ok samples are 100, 120, 150 → p50=120
    assert result.ttft_p50_ms == pytest.approx(120.0)
    # total tokens = 50 + 55 + 60 = 165
    # wall_clock is real time — we can't assert exact tok/s, but it should
    # be finite and non-negative for a > 0 wall.
    assert result.tokens_per_sec >= 0.0
    assert result.wall_clock_s >= 0.0


def test_run_level_handles_all_failures() -> None:
    def stub(*_a: object, **_k: object) -> RequestSample:
        return RequestSample(
            ttft_ms=0.0, duration_s=0.1, generation_tokens=0, ok=False, error="nope"
        )

    result = _run_level(
        base_url="http://stub",
        model="m",
        concurrency=2,
        n_requests=3,
        shared_prefix="s",
        suffixes=["u"],
        max_tokens=8,
        rss_sampler=None,
        server_name="mlx-lm",
        request_fn=stub,
    )
    assert result.ok_count == 0
    assert result.tokens_per_sec == 0.0
    assert result.ttft_p50_ms == 0.0
    assert result.ttft_p95_ms == 0.0


# ─── Markdown rendering ────────────────────────────────────────────────


def _sample_results() -> list[LevelResult]:
    """Synthetic results where vMLX wins on throughput and ties on RSS."""
    return [
        LevelResult(
            server="vmlx",
            concurrency=1,
            n_requests=4,
            ok_count=4,
            ttft_p50_ms=50.0,
            ttft_p95_ms=80.0,
            tokens_per_sec=100.0,
            peak_rss_mb=1200.0,
            wall_clock_s=2.0,
        ),
        LevelResult(
            server="mlx-lm",
            concurrency=1,
            n_requests=4,
            ok_count=4,
            ttft_p50_ms=60.0,
            ttft_p95_ms=100.0,
            tokens_per_sec=90.0,
            peak_rss_mb=1200.0,
            wall_clock_s=2.3,
        ),
        LevelResult(
            server="vmlx",
            concurrency=8,
            n_requests=32,
            ok_count=32,
            ttft_p50_ms=200.0,
            ttft_p95_ms=400.0,
            tokens_per_sec=800.0,
            peak_rss_mb=1800.0,
            wall_clock_s=4.0,
        ),
        LevelResult(
            server="mlx-lm",
            concurrency=8,
            n_requests=32,
            ok_count=32,
            ttft_p50_ms=250.0,
            ttft_p95_ms=500.0,
            tokens_per_sec=400.0,
            peak_rss_mb=1800.0,
            wall_clock_s=8.0,
        ),
    ]


def test_render_results_table_columns_present() -> None:
    md = _render_results_table(_sample_results())
    assert "| server | concurrency |" in md
    assert "| vmlx | 1 |" in md
    assert "| mlx-lm | 8 |" in md


def test_render_ratios_table_marks_vmlx_wins() -> None:
    md = _render_ratios_table(_sample_results())
    # concurrency=1: vmlx 100 tok/s vs mlx-lm 90 → 1.11×
    assert "1.11×" in md
    # concurrency=8: vmlx 800 vs mlx-lm 400 → 2.00×
    assert "2.00×" in md


def test_render_commentary_summarizes_wins() -> None:
    commentary = _render_commentary(_sample_results())
    # vMLX wins throughput on both levels in this synthetic data.
    assert "vMLX leads in 2 and trails in 0" in commentary
    assert "concurrency 1" in commentary
    assert "concurrency 8" in commentary


def test_render_commentary_detects_mlx_lm_win() -> None:
    """Commentary must honestly call out mlx-lm wins when the data says so."""
    results = [
        LevelResult(
            server="vmlx",
            concurrency=1,
            n_requests=4,
            ok_count=4,
            ttft_p50_ms=100.0,
            ttft_p95_ms=200.0,
            tokens_per_sec=50.0,  # loses
            peak_rss_mb=1000.0,
            wall_clock_s=5.0,
        ),
        LevelResult(
            server="mlx-lm",
            concurrency=1,
            n_requests=4,
            ok_count=4,
            ttft_p50_ms=80.0,
            ttft_p95_ms=160.0,
            tokens_per_sec=100.0,  # wins
            peak_rss_mb=1000.0,
            wall_clock_s=2.5,
        ),
    ]
    commentary = _render_commentary(results)
    assert "mlx-lm wins" in commentary
    assert "vMLX leads in 0 and trails in 1" in commentary


def test_render_caveats_flags_capped_concurrency() -> None:
    """When a concurrency level exceeds n_per_level, the reader needs to
    know the extra workers can't do useful work."""
    run = BenchmarkRun(
        timestamp="t",
        model="m",
        concurrency_levels=[1, 16],
        n_per_level=8,  # cap below max level
        max_tokens=8,
        shared_prefix_chars=100,
        suffix_chars=10,
        results=[],
        environment={},
    )
    caveats = _render_caveats(run)
    assert "capped at n_per_level (8)" in caveats


def test_render_caveats_omits_cap_when_unneeded() -> None:
    """If every concurrency level is at or below n_per_level, the cap
    caveat is a distraction — drop it."""
    run = BenchmarkRun(
        timestamp="t",
        model="m",
        concurrency_levels=[1, 4, 8],
        n_per_level=8,
        max_tokens=8,
        shared_prefix_chars=100,
        suffix_chars=10,
        results=[],
        environment={},
    )
    caveats = _render_caveats(run)
    assert "capped at n_per_level" not in caveats


def test_format_markdown_contains_sections() -> None:
    run = BenchmarkRun(
        timestamp="2026-04-22T00:00:00+00:00",
        model="mock/model",
        concurrency_levels=[1, 8],
        n_per_level=4,
        max_tokens=16,
        shared_prefix_chars=1200,
        suffix_chars=50,
        results=_sample_results(),
        environment={"python": "3.12.0", "platform": "macOS-14", "vmlx": "0.1.0", "mlx_lm": "0.31.3"},
        servers=[
            {"name": "vmlx", "version": "0.1.0", "port": "9001"},
            {"name": "mlx-lm", "version": "0.31.3", "port": "9002"},
        ],
    )
    md = _format_markdown(run, reproducibility_cmd="python -m vmlx.benchmarks.compare_mlx_lm --model mock/model")
    assert "# vMLX vs mlx-lm benchmark" in md
    assert "## Reproducibility" in md
    assert "## Results" in md
    assert "### Ratios (vmlx / mlx-lm)" in md
    assert "## Honest commentary" in md
    assert "## Caveats" in md
    assert "python -m vmlx.benchmarks.compare_mlx_lm --model mock/model" in md
    # Environment/server blocks should survive round-trip
    assert "`python`: 3.12.0" in md
    assert "`mlx_lm`: 0.31.3" in md


def test_format_markdown_is_valid_markdown_text() -> None:
    """Smoke check: the output must be plain text with no unclosed code
    fences. A stray ``` would break downstream rendering."""
    run = BenchmarkRun(
        timestamp="2026-04-22T00:00:00+00:00",
        model="m",
        concurrency_levels=[1],
        n_per_level=1,
        max_tokens=8,
        shared_prefix_chars=100,
        suffix_chars=10,
        results=_sample_results()[:2],
        environment={"python": "3.12", "platform": "x", "vmlx": "0.1.0", "mlx_lm": "0.31"},
        servers=[{"name": "vmlx", "version": "0.1", "port": "1"}],
    )
    md = _format_markdown(run, reproducibility_cmd="cmd")
    # Exactly 2 triple-backtick fences (one open + one close for the
    # reproducibility block).
    assert md.count("```") == 2


# ─── Server spec construction ──────────────────────────────────────────


def test_vmlx_server_spec_uses_batching_default() -> None:
    spec = _vmlx_server_spec(model="mock/model", port=1234, max_concurrent=8)
    assert spec.name == "vmlx"
    assert spec.port == 1234
    assert "--engine" in spec.cmd
    i = spec.cmd.index("--engine")
    assert spec.cmd[i + 1] == "batching"
    assert "--max-concurrent" in spec.cmd
    i = spec.cmd.index("--max-concurrent")
    assert spec.cmd[i + 1] == "8"


# ─── BenchmarkRun round-trip ───────────────────────────────────────────


def test_benchmark_run_to_dict_round_trips_json() -> None:
    run = BenchmarkRun(
        timestamp="2026-04-22T00:00:00+00:00",
        model="m",
        concurrency_levels=[1],
        n_per_level=1,
        max_tokens=8,
        shared_prefix_chars=100,
        suffix_chars=10,
        results=_sample_results()[:1],
        environment={"python": "3.12"},
    )
    d = run.to_dict()
    # Must be JSON-serializable.
    s = json.dumps(d)
    reloaded = cast(dict[str, object], json.loads(s))
    assert reloaded["model"] == "m"
    assert reloaded["concurrency_levels"] == [1]
