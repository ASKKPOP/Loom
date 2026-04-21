"""CLI entry point for vMLX benchmarks.

Usage::

    python -m vmlx.benchmarks.run --engine single \\
        --model mlx-community/Qwen2.5-0.5B-Instruct-4bit --n 20

By default, prints the full JSON report to stdout and appends a single-line
summary to ``vmlx/benchmarks/history.jsonl`` for tracking over time.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vmlx.benchmarks.registry import available_engines, build_engine
from vmlx.benchmarks.runner import DEFAULT_PROMPT, run_benchmark

DEFAULT_HISTORY_PATH = "vmlx/benchmarks/history.jsonl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m vmlx.benchmarks.run",
        description="Run a fixed workload against a vMLX engine and emit a JSON report.",
    )
    parser.add_argument(
        "--engine",
        choices=available_engines(),
        required=True,
        help="Engine implementation to benchmark.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model id (e.g. mlx-community/Qwen2.5-0.5B-Instruct-4bit).",
    )
    parser.add_argument(
        "--n",
        type=int,
        required=True,
        help="Number of requests to run.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=100,
        help="Tokens to generate per request (default: 100).",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt used for every request (default: built-in counting prompt).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report JSON to this path instead of stdout.",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=Path(DEFAULT_HISTORY_PATH),
        help=(
            "Append a one-line summary to this file for historical tracking "
            f"(default: {DEFAULT_HISTORY_PATH}; use --no-history to skip)."
        ),
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Do not append to the history file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    engine = build_engine(args.engine, args.model)
    print(f"vmlx-bench: loading {args.model}...", file=sys.stderr)
    engine.load()
    try:
        print(
            f"vmlx-bench: running engine={args.engine} n={args.n} "
            f"max_tokens={args.max_tokens}...",
            file=sys.stderr,
        )
        report = run_benchmark(
            engine,
            engine_name=args.engine,
            n=args.n,
            max_tokens=args.max_tokens,
            prompt=args.prompt,
        )
    finally:
        engine.unload()

    report_json = report.to_json()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report_json + "\n", encoding="utf-8")
        print(f"vmlx-bench: wrote report to {args.output}", file=sys.stderr)
    else:
        print(report_json)

    if not args.no_history:
        args.history.parent.mkdir(parents=True, exist_ok=True)
        report.append_to_history(str(args.history))
        print(f"vmlx-bench: appended to {args.history}", file=sys.stderr)

    summary = (
        f"vmlx-bench: DONE engine={report.engine} "
        f"tps={report.tokens_per_sec:.1f} "
        f"ttft_p50={report.ttft_p50_ms:.1f}ms "
        f"ttft_p95={report.ttft_p95_ms:.1f}ms "
        f"peak_rss={report.peak_rss_mb:.0f}MB "
        f"total={report.total_duration_s:.1f}s"
    )
    print(summary, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
