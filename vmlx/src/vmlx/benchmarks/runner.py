"""Benchmark runner — executes a workload against an engine and reports metrics."""

from __future__ import annotations

import platform as platform_mod
import resource
import sys
import time
from datetime import UTC, datetime

from vmlx import __version__ as vmlx_version
from vmlx.benchmarks.registry import EngineProtocol
from vmlx.benchmarks.report import BenchmarkReport, RequestMetrics

DEFAULT_PROMPT = (
    "Count to ten: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10. "
    "Now describe each number briefly in a single short sentence each."
)


def _peak_rss_mb() -> float:
    """Return peak process RSS in megabytes.

    getrusage().ru_maxrss is bytes on macOS, kilobytes on Linux.
    """
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return float(rss) / (1024 * 1024)
    return float(rss) / 1024  # Linux: KB → MB


def _percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile. Returns 0.0 for empty input."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    # statistics.quantiles works but treats n=N slices differently for tiny N;
    # compute directly for stable behavior at small N.
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def run_benchmark(
    engine: EngineProtocol,
    *,
    engine_name: str,
    n: int,
    max_tokens: int = 100,
    prompt: str = DEFAULT_PROMPT,
) -> BenchmarkReport:
    """Run N generate() calls and build a BenchmarkReport.

    `engine` must already be loaded before calling this. `engine_name` is
    recorded verbatim in the report for historical tracking.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n!r}")
    if max_tokens <= 0:
        raise ValueError(f"max_tokens must be positive, got {max_tokens!r}")

    per_request: list[RequestMetrics] = []
    total_generation_tokens = 0
    start_wall = time.perf_counter()
    for i in range(n):
        r = engine.generate(prompt, max_tokens=max_tokens)
        per_request.append(
            RequestMetrics(
                i=i,
                ttft_ms=r.ttft_ms,
                generation_tokens=r.generation_tokens,
                tokens_per_second=r.tokens_per_second,
                duration_s=r.duration_s,
                peak_memory_mb=r.peak_memory_mb,
                finish_reason=r.finish_reason,
            )
        )
        total_generation_tokens += r.generation_tokens
    total_duration_s = time.perf_counter() - start_wall

    ttfts = [r.ttft_ms for r in per_request]
    aggregate_tps = (
        total_generation_tokens / total_duration_s if total_duration_s > 0 else 0.0
    )

    return BenchmarkReport(
        timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
        engine=engine_name,
        model=engine.model_id,
        n=n,
        max_tokens=max_tokens,
        prompt_chars=len(prompt),
        ttft_p50_ms=_percentile(ttfts, 50.0),
        ttft_p95_ms=_percentile(ttfts, 95.0),
        tokens_per_sec=aggregate_tps,
        peak_rss_mb=_peak_rss_mb(),
        total_duration_s=total_duration_s,
        vmlx_version=vmlx_version,
        python_version=platform_mod.python_version(),
        platform=platform_mod.platform(),
        per_request=per_request,
    )


__all__ = ["DEFAULT_PROMPT", "run_benchmark"]
