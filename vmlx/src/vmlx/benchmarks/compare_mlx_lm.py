"""Head-to-head benchmark: vMLX vs mlx-lm on the same model, apples to apples.

Both servers expose an OpenAI-compatible ``/v1/chat/completions`` endpoint.
We boot each in turn, send a shared system prompt + varied user suffixes at
several concurrency levels, and record aggregate tokens/sec, TTFT p50/p95,
and peak process RSS. The report is emitted as markdown — no specific ratio
is gated on, so the numbers can show honestly where vMLX wins, ties, or
loses.

Usage::

    python -m vmlx.benchmarks.compare_mlx_lm \\
        --model mlx-community/Qwen2.5-0.5B-Instruct-4bit \\
        --concurrency 1,4,8,16 \\
        --requests-per-level 8 \\
        --output docs/vmlx/benchmarks/vs-mlx-lm.md
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import platform as platform_mod
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vmlx import __version__ as vmlx_version

# ─── Data classes ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ServerSpec:
    """Everything needed to stand up one server under test."""

    name: str  # "vmlx" or "mlx-lm"
    cmd: list[str]
    port: int
    version: str  # e.g. "0.1.0" for vmlx or "0.31.3" for mlx-lm


@dataclass(frozen=True)
class RequestSample:
    """One completed request's timings."""

    ttft_ms: float
    duration_s: float
    generation_tokens: int
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class LevelResult:
    """Aggregated stats for one concurrency level on one server."""

    server: str
    concurrency: int
    n_requests: int
    ok_count: int
    ttft_p50_ms: float
    ttft_p95_ms: float
    tokens_per_sec: float  # aggregate (total_gen_tokens / wall_clock_s)
    peak_rss_mb: float
    wall_clock_s: float


@dataclass(frozen=True)
class BenchmarkRun:
    """All levels for both servers plus environment info."""

    timestamp: str
    model: str
    concurrency_levels: list[int]
    n_per_level: int
    max_tokens: int
    shared_prefix_chars: int
    suffix_chars: int
    results: list[LevelResult]
    environment: dict[str, str]
    servers: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        return d


# ─── Port + readiness helpers ──────────────────────────────────────────


def _free_port() -> int:
    """Bind an ephemeral port, close, and return — caller races on reuse,
    but this is good enough for non-adversarial local benchmarks."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_for_readiness(base_url: str, timeout_s: float = 120.0) -> None:
    """Block until ``GET /v1/models`` returns 200, or raise TimeoutError.

    We probe /v1/models rather than /health because mlx-lm doesn't expose a
    health endpoint — the OpenAI listing is the lowest common denominator.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"{base_url}/v1/models", timeout=2.0
            ) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    raise TimeoutError(
        f"server at {base_url} did not become ready within {timeout_s:.0f}s"
    )


# ─── RSS sampling ──────────────────────────────────────────────────────


def _macos_hw_info() -> str:
    """Return 'Apple M4 Max (Mac16,9)' style info on macOS, or 'unknown'
    elsewhere. Purely informational — used in the markdown report so a
    reader can tell which chip the numbers came from."""
    if sys.platform != "darwin":
        return "unknown"
    try:
        brand = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        brand = "unknown-cpu"
    try:
        model = subprocess.check_output(
            ["sysctl", "-n", "hw.model"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        model = "unknown-model"
    return f"{brand} ({model})"


def _rss_mb(pid: int) -> float:
    """Return RSS of ``pid`` in MB, or 0.0 if the process is gone.

    Uses ``ps -o rss= -p <pid>`` so we don't pull in psutil just for this.
    macOS `ps` reports RSS in KB.
    """
    try:
        out = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(pid)],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        ).strip()
        if not out:
            return 0.0
        return float(out) / 1024.0  # KB → MB
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return 0.0


class _PeakRSSSampler:
    """Samples RSS of a pid on a background thread until stopped."""

    def __init__(self, pid: int, interval_s: float = 0.25) -> None:
        self.pid = pid
        self.interval_s = interval_s
        self.peak_mb = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            v = _rss_mb(self.pid)
            if v > self.peak_mb:
                self.peak_mb = v
            self._stop.wait(self.interval_s)


# ─── Single request (streaming /v1/chat/completions) ───────────────────


def _stream_chat_completion(
    base_url: str,
    model: str,
    system: str,
    user: str,
    *,
    max_tokens: int,
    timeout_s: float = 120.0,
) -> RequestSample:
    """Send one chat-completion request with ``stream=True`` and measure:

    * TTFT = time from ``urlopen`` return to first SSE delta with content
    * generation_tokens = count of content deltas across the stream
    * duration_s = time from open to final ``data: [DONE]``

    We count content deltas as a cross-server token proxy. It is not exact
    token count (tokenizer-dependent), but it is consistent across servers
    and good enough for aggregate tokens/sec comparisons.
    """
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "stream": True,
            "temperature": 0.0,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            ttft_ms: float | None = None
            gen_tokens = 0
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                if not line.startswith("data: "):
                    continue
                body = line[len("data: "):]
                if body == "[DONE]":
                    break
                try:
                    chunk = json.loads(body)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - t0) * 1000.0
                    gen_tokens += 1
            duration_s = time.perf_counter() - t0
            if ttft_ms is None:
                # Server returned only empty deltas or finish-without-content.
                # Still a response — record duration, zero gen tokens.
                return RequestSample(
                    ttft_ms=duration_s * 1000.0,
                    duration_s=duration_s,
                    generation_tokens=0,
                    ok=False,
                    error="no content deltas received",
                )
            return RequestSample(
                ttft_ms=ttft_ms,
                duration_s=duration_s,
                generation_tokens=gen_tokens,
                ok=True,
            )
    except (
        urllib.error.URLError,
        ConnectionError,
        OSError,
        TimeoutError,
    ) as e:
        return RequestSample(
            ttft_ms=0.0,
            duration_s=time.perf_counter() - t0,
            generation_tokens=0,
            ok=False,
            error=repr(e),
        )


# ─── Concurrency level runner ──────────────────────────────────────────


def _run_level(
    *,
    base_url: str,
    model: str,
    concurrency: int,
    n_requests: int,
    shared_prefix: str,
    suffixes: list[str],
    max_tokens: int,
    rss_sampler: _PeakRSSSampler | None,
    server_name: str,
    request_fn: Callable[..., RequestSample] = _stream_chat_completion,
) -> LevelResult:
    """Fire ``n_requests`` in parallel with ``concurrency`` workers."""
    from concurrent.futures import ThreadPoolExecutor

    samples: list[RequestSample] = []
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [
            ex.submit(
                request_fn,
                base_url,
                model,
                shared_prefix,
                suffixes[i % len(suffixes)],
                max_tokens=max_tokens,
            )
            for i in range(n_requests)
        ]
        for fut in futures:
            samples.append(fut.result())
    wall_s = time.perf_counter() - start

    ok = [s for s in samples if s.ok]
    total_tokens = sum(s.generation_tokens for s in ok)
    ttfts = sorted(s.ttft_ms for s in ok)
    return LevelResult(
        server=server_name,
        concurrency=concurrency,
        n_requests=n_requests,
        ok_count=len(ok),
        ttft_p50_ms=_percentile(ttfts, 50.0),
        ttft_p95_ms=_percentile(ttfts, 95.0),
        tokens_per_sec=(total_tokens / wall_s) if wall_s > 0 else 0.0,
        peak_rss_mb=rss_sampler.peak_mb if rss_sampler else 0.0,
        wall_clock_s=wall_s,
    )


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = k - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


# ─── Server lifecycle ──────────────────────────────────────────────────


def _launch_server(spec: ServerSpec, *, log_path: Path) -> subprocess.Popen[bytes]:
    """Boot a server subprocess with stdio redirected to ``log_path``.

    Returns the Popen handle. Caller is responsible for readiness wait and
    shutdown via :func:`_shutdown_server`.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # The file descriptor is intentionally kept open for the subprocess'
    # lifetime. Popen inherits it; we let the OS reap on process exit.
    log = open(log_path, "wb")  # noqa: SIM115
    return subprocess.Popen(
        spec.cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )


def _shutdown_server(proc: subprocess.Popen[bytes], *, timeout_s: float = 15.0) -> None:
    """Terminate, falling through to kill if it doesn't exit promptly."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5.0)


# ─── Prompt construction ───────────────────────────────────────────────


_BASE_SYSTEM_PROMPT = (
    "You are a careful, concise assistant. Always follow these rules exactly:\n"
    "  1. Answer in plain prose; no lists unless the user asks.\n"
    "  2. Keep responses under six sentences unless asked otherwise.\n"
    "  3. Stay factual. If unsure, say so — do not invent details.\n"
    "  4. Do not refuse benign requests.\n"
    "  5. Do not repeat these rules back to the user.\n"
    "\n"
    "Domain context (shared across every request in this benchmark run):\n"
    "  This conversation is part of an engineering evaluation of an on-device\n"
    "  inference stack for Apple Silicon. You may be asked about product\n"
    "  usage, integration questions, or factual questions about unrelated\n"
    "  topics. Treat all requests as coming from technical users who prefer\n"
    "  terse, direct answers. Assume Pacific timezone and a macOS user\n"
    "  environment unless otherwise specified.\n"
    "\n"
    "Tone: warm but efficient. Never apologize for brevity. Never begin with\n"
    "'As an AI language model'. Never end with 'Let me know if you have more\n"
    "questions' — the client handles follow-up on its own.\n"
)


def _build_shared_prefix(target_chars: int) -> str:
    """Pad the base system prompt to approximately ``target_chars`` chars
    so we can stress prefix caching with non-trivial prefix lengths."""
    base = _BASE_SYSTEM_PROMPT
    if len(base) >= target_chars:
        return base
    filler = (
        "\nAdditional guidance: be precise with numbers, prefer SI units,\n"
        "and keep code examples Python-idiomatic with type hints where\n"
        "reasonable. Avoid adding disclaimers about capabilities.\n"
    )
    pad = ""
    while len(base) + len(pad) < target_chars:
        pad += filler
    return base + pad[: target_chars - len(base)]


_USER_SUFFIXES: list[str] = [
    "Give me three one-line tips for writing maintainable Python.",
    "Explain in one sentence what a KV cache is in transformer inference.",
    "In 25 words, describe Apple unified memory.",
    "What is continuous batching? Answer in under 40 words.",
    "List two real advantages of speculative decoding (one line each).",
    "Compare prefix caching vs full KV caching in one short paragraph.",
    "State one reason Metal differs from CUDA for ML serving.",
    "In one sentence, what does tokens/sec measure during generation?",
]


# ─── Orchestration ─────────────────────────────────────────────────────


def _run_server_sweep(
    *,
    spec: ServerSpec,
    model: str,
    concurrency_levels: Sequence[int],
    n_per_level: int,
    max_tokens: int,
    shared_prefix: str,
    suffixes: list[str],
    log_dir: Path,
) -> list[LevelResult]:
    """Boot spec, run all concurrency levels, shut down. Returns all results."""
    results: list[LevelResult] = []
    log_path = log_dir / f"{spec.name}.log"
    print(
        f"[compare] launching {spec.name} on port {spec.port} (logs -> {log_path})",
        file=sys.stderr,
        flush=True,
    )
    proc = _launch_server(spec, log_path=log_path)
    try:
        base_url = f"http://127.0.0.1:{spec.port}"
        _wait_for_readiness(base_url, timeout_s=180.0)
        print(f"[compare] {spec.name} ready", file=sys.stderr, flush=True)
        sampler = _PeakRSSSampler(proc.pid)
        sampler.start()
        try:
            for c in concurrency_levels:
                print(
                    f"[compare]   {spec.name} concurrency={c} n={n_per_level}...",
                    file=sys.stderr,
                    flush=True,
                )
                results.append(
                    _run_level(
                        base_url=base_url,
                        model=model,
                        concurrency=c,
                        n_requests=n_per_level,
                        shared_prefix=shared_prefix,
                        suffixes=suffixes,
                        max_tokens=max_tokens,
                        rss_sampler=sampler,
                        server_name=spec.name,
                    )
                )
        finally:
            sampler.stop()
    finally:
        _shutdown_server(proc)
        print(f"[compare] {spec.name} shut down", file=sys.stderr, flush=True)
    return results


def _vmlx_server_spec(
    *, model: str, port: int, max_concurrent: int
) -> ServerSpec:
    return ServerSpec(
        name="vmlx",
        cmd=[
            sys.executable,
            "-m",
            "vmlx.cli",
            "serve",
            model,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--engine",
            "batching",
            "--max-concurrent",
            str(max_concurrent),
        ],
        port=port,
        version=vmlx_version,
    )


def _mlx_lm_server_spec(
    *,
    model: str,
    port: int,
    decode_concurrency: int,
    prompt_concurrency: int,
    prompt_cache_size: int,
) -> ServerSpec:
    try:
        import mlx_lm  # type: ignore[import-not-found]

        mlx_lm_version = getattr(mlx_lm, "__version__", "unknown")
    except ImportError:
        mlx_lm_version = "not-installed"
    return ServerSpec(
        name="mlx-lm",
        cmd=[
            sys.executable,
            "-m",
            "mlx_lm",
            "server",
            "--model",
            model,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "WARNING",
            "--decode-concurrency",
            str(decode_concurrency),
            "--prompt-concurrency",
            str(prompt_concurrency),
            "--prompt-cache-size",
            str(prompt_cache_size),
        ],
        port=port,
        version=mlx_lm_version,
    )


# ─── Markdown emitter ──────────────────────────────────────────────────


def _format_markdown(run: BenchmarkRun, *, reproducibility_cmd: str) -> str:
    """Render a self-contained markdown doc: header, reproducibility block,
    per-concurrency table with ratios, and an honest commentary section."""
    lines: list[str] = []
    lines.append("# vMLX vs mlx-lm benchmark")
    lines.append("")
    lines.append(f"_Generated {run.timestamp}_")
    lines.append("")
    lines.append("Head-to-head on the same model and identical workload.")
    lines.append(
        "We boot each server, fire a shared system prompt + varied user "
        "suffixes at several concurrency levels, and measure aggregate "
        "tokens/sec, TTFT p50/p95, and peak server-process RSS."
    )
    lines.append("")

    # Reproducibility
    lines.append("## Reproducibility")
    lines.append("")
    lines.append("```bash")
    lines.append(reproducibility_cmd)
    lines.append("```")
    lines.append("")
    lines.append("**Environment**")
    lines.append("")
    for k, v in run.environment.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("**Servers**")
    lines.append("")
    for s in run.servers:
        lines.append(f"- `{s['name']}` — version `{s['version']}`, port `{s['port']}`")
    lines.append("")
    lines.append("**Workload**")
    lines.append("")
    lines.append(f"- model: `{run.model}`")
    lines.append(f"- concurrency levels: {run.concurrency_levels}")
    lines.append(f"- requests per level: {run.n_per_level}")
    lines.append(f"- max_tokens: {run.max_tokens}")
    lines.append(
        f"- shared system prompt: ~{run.shared_prefix_chars} chars "
        f"(stresses prefix caching)"
    )
    lines.append(f"- user suffix length: ~{run.suffix_chars} chars")
    lines.append("")

    # Results table
    lines.append("## Results")
    lines.append("")
    lines.append(_render_results_table(run.results))
    lines.append("")

    # Ratios table
    lines.append("### Ratios (vmlx / mlx-lm)")
    lines.append("")
    lines.append(_render_ratios_table(run.results))
    lines.append("")

    # Commentary
    lines.append("## Honest commentary")
    lines.append("")
    lines.append(_render_commentary(run.results))
    lines.append("")

    # Caveats
    lines.append("## Caveats")
    lines.append("")
    lines.append(_render_caveats(run))
    lines.append("")

    return "\n".join(lines)


def _render_caveats(run: BenchmarkRun) -> str:
    """Spell out the limits of this run so a reader can size up the numbers."""
    lines = [
        "- **Single run, no warm-up averaging.** Each data point is from "
        "one sweep. Rerun to confirm before drawing conclusions on tight "
        "margins.",
        "- **Token count is a proxy.** We count streamed content deltas "
        "as a cross-server token estimate — it's consistent but not exact. "
        "Absolute tok/s should be compared *between* servers in this "
        "report, not against externally measured figures.",
    ]
    # Note when effective concurrency is bounded by n_per_level.
    if max(run.concurrency_levels) > run.n_per_level:
        lines.append(
            f"- **Effective concurrency is capped at n_per_level "
            f"({run.n_per_level}).** Levels above {run.n_per_level} can't "
            "utilize more than that many simultaneous requests in this run, "
            "so their numbers should match. Bump `--requests-per-level` to "
            "saturate higher concurrency."
        )
    lines.append(
        "- **Model is small (0.5B, 4-bit).** Larger models stress prefill "
        "and memory differently; rerun on production-sized weights before "
        "planning capacity."
    )
    lines.append(
        "- **Workload is synthetic.** Prompts share a ~1.2k-char system "
        "prefix; real traffic may have very different prefix/suffix ratios, "
        "which will shift cache hit rates."
    )
    return "\n".join(lines)


def _render_results_table(results: list[LevelResult]) -> str:
    """Render a flat table: one row per (server, concurrency)."""
    lines = [
        "| server | concurrency | ok/n | agg tok/s | TTFT p50 ms | TTFT p95 ms | peak RSS MB | wall s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(results, key=lambda x: (x.concurrency, x.server)):
        lines.append(
            f"| {r.server} | {r.concurrency} | {r.ok_count}/{r.n_requests} "
            f"| {r.tokens_per_sec:.1f} | {r.ttft_p50_ms:.1f} "
            f"| {r.ttft_p95_ms:.1f} | {r.peak_rss_mb:.0f} "
            f"| {r.wall_clock_s:.2f} |"
        )
    return "\n".join(lines)


def _render_ratios_table(results: list[LevelResult]) -> str:
    """Ratios = vmlx metric / mlx-lm metric, paired by concurrency.

    For tok/s, ratio > 1 means vMLX wins.
    For TTFT p50/p95 and peak RSS, ratio < 1 means vMLX wins (lower is better).
    """
    by_c: dict[int, dict[str, LevelResult]] = {}
    for r in results:
        by_c.setdefault(r.concurrency, {})[r.server] = r

    lines = [
        "| concurrency | tok/s ratio (↑ favors vmlx) | TTFT p50 ratio (↓ favors vmlx) | TTFT p95 ratio (↓ favors vmlx) | peak RSS ratio (↓ favors vmlx) |",
        "|---:|---:|---:|---:|---:|",
    ]
    for c in sorted(by_c.keys()):
        pair = by_c[c]
        v = pair.get("vmlx")
        m = pair.get("mlx-lm")
        if v is None or m is None:
            lines.append(f"| {c} | n/a | n/a | n/a | n/a |")
            continue
        tps = _safe_ratio(v.tokens_per_sec, m.tokens_per_sec)
        t50 = _safe_ratio(v.ttft_p50_ms, m.ttft_p50_ms)
        t95 = _safe_ratio(v.ttft_p95_ms, m.ttft_p95_ms)
        rss = _safe_ratio(v.peak_rss_mb, m.peak_rss_mb)
        lines.append(
            f"| {c} | {_fmt_ratio(tps)} | {_fmt_ratio(t50)} "
            f"| {_fmt_ratio(t95)} | {_fmt_ratio(rss)} |"
        )
    return "\n".join(lines)


def _safe_ratio(num: float, denom: float) -> float | None:
    if denom <= 0.0:
        return None
    return num / denom


def _fmt_ratio(r: float | None) -> str:
    if r is None:
        return "n/a"
    return f"{r:.2f}×"


def _render_commentary(results: list[LevelResult]) -> str:
    """Auto-generate a per-level sentence without editorializing beyond
    what the measured numbers say. The reader can draw their own conclusions.
    """
    by_c: dict[int, dict[str, LevelResult]] = {}
    for r in results:
        by_c.setdefault(r.concurrency, {})[r.server] = r

    lines = []
    wins_tps = 0
    losses_tps = 0
    for c in sorted(by_c.keys()):
        pair = by_c[c]
        v = pair.get("vmlx")
        m = pair.get("mlx-lm")
        if v is None or m is None:
            continue
        tps_ratio = _safe_ratio(v.tokens_per_sec, m.tokens_per_sec)
        ttft_ratio = _safe_ratio(v.ttft_p50_ms, m.ttft_p50_ms)
        if tps_ratio is None or ttft_ratio is None:
            continue
        verdict_tps = (
            "vMLX wins"
            if tps_ratio > 1.05
            else ("mlx-lm wins" if tps_ratio < 0.95 else "parity")
        )
        verdict_ttft = (
            "vMLX wins"
            if ttft_ratio < 0.95
            else ("mlx-lm wins" if ttft_ratio > 1.05 else "parity")
        )
        if verdict_tps == "vMLX wins":
            wins_tps += 1
        elif verdict_tps == "mlx-lm wins":
            losses_tps += 1
        lines.append(
            f"- **concurrency {c}** — throughput: {verdict_tps} "
            f"({_fmt_ratio(tps_ratio)}); TTFT p50: {verdict_ttft} "
            f"({_fmt_ratio(ttft_ratio)})."
        )

    summary = (
        f"Across {wins_tps + losses_tps} head-to-head throughput "
        f"comparisons, vMLX leads in {wins_tps} and trails in {losses_tps}. "
        "Numbers reflect a single run on the listed hardware; treat "
        "differences under ~10% as noise and rerun to confirm before "
        "acting on anything tighter."
    )
    return "\n".join(lines) + "\n\n" + summary


# ─── CLI ───────────────────────────────────────────────────────────────


def _parse_concurrency(s: str) -> list[int]:
    """Parse '1,4,8,16' → [1,4,8,16], rejecting non-positive values."""
    out: list[int] = []
    for piece in s.split(","):
        piece = piece.strip()
        if not piece:
            continue
        v = int(piece)
        if v <= 0:
            raise argparse.ArgumentTypeError(
                f"concurrency values must be positive, got {v}"
            )
        out.append(v)
    if not out:
        raise argparse.ArgumentTypeError("empty concurrency list")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m vmlx.benchmarks.compare_mlx_lm",
        description=(
            "Head-to-head throughput / latency benchmark: vMLX vs mlx-lm "
            "against the same model at several concurrency levels."
        ),
    )
    p.add_argument("--model", required=True, help="MLX model id to serve on both.")
    p.add_argument(
        "--concurrency",
        type=_parse_concurrency,
        default=[1, 4, 8, 16],
        help="Comma-separated list of concurrency levels (default: 1,4,8,16).",
    )
    p.add_argument(
        "--requests-per-level",
        type=int,
        default=8,
        help="Number of requests per concurrency level per server (default: 8).",
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=64,
        help="max_tokens on every chat completion (default: 64).",
    )
    p.add_argument(
        "--shared-prefix-chars",
        type=int,
        default=1200,
        help="Approximate shared system prompt length (default: 1200).",
    )
    p.add_argument(
        "--vmlx-port",
        type=int,
        default=0,
        help="Port for vmlx serve (0 = auto-pick).",
    )
    p.add_argument(
        "--mlx-lm-port",
        type=int,
        default=0,
        help="Port for mlx_lm server (0 = auto-pick).",
    )
    p.add_argument(
        "--max-concurrent",
        type=int,
        default=32,
        help="vmlx --max-concurrent value (default: 32).",
    )
    p.add_argument(
        "--decode-concurrency",
        type=int,
        default=16,
        help="mlx-lm --decode-concurrency (default: 16).",
    )
    p.add_argument(
        "--prompt-concurrency",
        type=int,
        default=4,
        help="mlx-lm --prompt-concurrency (default: 4).",
    )
    p.add_argument(
        "--prompt-cache-size",
        type=int,
        default=16,
        help="mlx-lm --prompt-cache-size (default: 16).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("docs/vmlx/benchmarks/vs-mlx-lm.md"),
        help="Path for the markdown report (default: docs/vmlx/benchmarks/vs-mlx-lm.md).",
    )
    p.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional raw JSON dump of the run for further analysis.",
    )
    p.add_argument(
        "--log-dir",
        type=Path,
        default=Path("vmlx/benchmarks/compare_logs"),
        help="Directory for server stdout/stderr captures.",
    )
    p.add_argument(
        "--skip-vmlx",
        action="store_true",
        help="Skip the vMLX run (useful for iterating on mlx-lm-only baselines).",
    )
    p.add_argument(
        "--skip-mlx-lm",
        action="store_true",
        help="Skip the mlx-lm run.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.skip_vmlx and args.skip_mlx_lm:
        print("refusing to skip both servers — nothing to benchmark", file=sys.stderr)
        return 2

    vmlx_port = args.vmlx_port or _free_port()
    mlx_lm_port = args.mlx_lm_port or _free_port()
    # Ensure distinct ports even if both are passed as 0 and _free_port
    # coincides (vanishingly unlikely, but deterministic cost to check).
    if vmlx_port == mlx_lm_port:
        mlx_lm_port = _free_port()

    shared_prefix = _build_shared_prefix(args.shared_prefix_chars)
    suffixes = _USER_SUFFIXES
    suffix_chars = int(statistics.mean(len(s) for s in suffixes))

    env_info = {
        "python": platform_mod.python_version(),
        "platform": platform_mod.platform(),
        "hardware": _macos_hw_info(),
        "vmlx": vmlx_version,
    }
    try:
        import mlx_lm  # type: ignore[import-not-found]

        env_info["mlx_lm"] = getattr(mlx_lm, "__version__", "unknown")
    except ImportError:
        env_info["mlx_lm"] = "not-installed"

    all_results: list[LevelResult] = []
    servers_used: list[dict[str, str]] = []

    if not args.skip_vmlx:
        vmlx_spec = _vmlx_server_spec(
            model=args.model,
            port=vmlx_port,
            max_concurrent=args.max_concurrent,
        )
        servers_used.append(
            {"name": vmlx_spec.name, "version": vmlx_spec.version, "port": str(vmlx_port)}
        )
        all_results.extend(
            _run_server_sweep(
                spec=vmlx_spec,
                model=args.model,
                concurrency_levels=args.concurrency,
                n_per_level=args.requests_per_level,
                max_tokens=args.max_tokens,
                shared_prefix=shared_prefix,
                suffixes=suffixes,
                log_dir=args.log_dir,
            )
        )

    if not args.skip_mlx_lm:
        mlx_lm_spec = _mlx_lm_server_spec(
            model=args.model,
            port=mlx_lm_port,
            decode_concurrency=args.decode_concurrency,
            prompt_concurrency=args.prompt_concurrency,
            prompt_cache_size=args.prompt_cache_size,
        )
        servers_used.append(
            {"name": mlx_lm_spec.name, "version": mlx_lm_spec.version, "port": str(mlx_lm_port)}
        )
        all_results.extend(
            _run_server_sweep(
                spec=mlx_lm_spec,
                model=args.model,
                concurrency_levels=args.concurrency,
                n_per_level=args.requests_per_level,
                max_tokens=args.max_tokens,
                shared_prefix=shared_prefix,
                suffixes=suffixes,
                log_dir=args.log_dir,
            )
        )

    run = BenchmarkRun(
        timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
        model=args.model,
        concurrency_levels=list(args.concurrency),
        n_per_level=args.requests_per_level,
        max_tokens=args.max_tokens,
        shared_prefix_chars=len(shared_prefix),
        suffix_chars=suffix_chars,
        results=all_results,
        environment=env_info,
        servers=servers_used,
    )

    repro_cmd = (
        f"python -m vmlx.benchmarks.compare_mlx_lm \\\n"
        f"  --model {args.model} \\\n"
        f"  --concurrency {','.join(str(c) for c in args.concurrency)} \\\n"
        f"  --requests-per-level {args.requests_per_level} \\\n"
        f"  --max-tokens {args.max_tokens}"
    )
    md = _format_markdown(run, reproducibility_cmd=repro_cmd)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(f"[compare] wrote report to {args.output}", file=sys.stderr)

    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(run.to_dict(), indent=2) + "\n", encoding="utf-8"
        )
        print(f"[compare] wrote raw JSON to {args.json_output}", file=sys.stderr)

    # Also echo the results table to stdout so the terminal user sees
    # something useful without opening the markdown file.
    print(_render_results_table(all_results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
