"""Benchmark report schema.

`BenchmarkReport` is the canonical shape appended to
`vmlx/benchmarks/history.jsonl` and emitted as JSON from the CLI.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RequestMetrics:
    """Per-request measurements within a benchmark run."""

    i: int
    ttft_ms: float
    generation_tokens: int
    tokens_per_second: float
    duration_s: float
    peak_memory_mb: float
    finish_reason: str | None


@dataclass(frozen=True)
class BenchmarkReport:
    """Complete benchmark report, appended one per line to history.jsonl."""

    timestamp: str
    engine: str
    model: str
    n: int
    max_tokens: int
    prompt_chars: int
    ttft_p50_ms: float
    ttft_p95_ms: float
    tokens_per_sec: float
    peak_rss_mb: float
    total_duration_s: float
    vmlx_version: str
    python_version: str
    platform: str
    per_request: list[RequestMetrics] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def append_to_history(self, path: str) -> None:
        """Append this report as a single JSON line to `path`."""
        with open(path, "a", encoding="utf-8") as f:
            f.write(self.to_json(indent=None))
            f.write("\n")
