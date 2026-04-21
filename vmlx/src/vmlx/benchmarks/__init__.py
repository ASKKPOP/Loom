"""Benchmark harness for vMLX engines.

The harness runs a fixed workload (N prompts, same prompt each time, fixed
max_tokens) against a named engine and produces a JSON report. Every vMLX
improvement benchmarks against this yardstick.

Usage::

    python -m vmlx.benchmarks.run --engine single \\
        --model mlx-community/Qwen2.5-0.5B-Instruct-4bit --n 20

See :mod:`vmlx.benchmarks.run` for the CLI and :mod:`vmlx.benchmarks.report`
for the report schema.
"""

from __future__ import annotations

from vmlx.benchmarks.report import BenchmarkReport, RequestMetrics
from vmlx.benchmarks.runner import run_benchmark

__all__ = ["BenchmarkReport", "RequestMetrics", "run_benchmark"]
