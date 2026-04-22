"""vMLX command-line entry point."""

from __future__ import annotations

import argparse
import sys

from vmlx import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vmlx",
        description="vMLX — high-throughput MLX serving engine for Apple Silicon",
    )
    parser.add_argument(
        "--version", action="version", version=f"vmlx {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    serve = subparsers.add_parser(
        "serve",
        help="Serve an MLX model over an OpenAI-compatible HTTP API.",
    )
    serve.add_argument("model", help="Model id (e.g. mlx-community/...)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--engine",
        choices=("single", "batching"),
        default="batching",
        help=(
            "Inference engine. 'batching' (default): continuous-batched, "
            "higher aggregate throughput under concurrent load. 'single': "
            "one request at a time, lowest per-request latency."
        ),
    )
    serve.add_argument(
        "--max-concurrent",
        type=int,
        default=32,
        help=(
            "Max concurrent requests the batching engine schedules at once. "
            "Ignored when --engine=single. Default: 32."
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        from vmlx.api.server import run_server

        print(
            (
                f"vmlx serve: model={args.model} host={args.host} "
                f"port={args.port} engine={args.engine} "
                f"max_concurrent={args.max_concurrent}"
            ),
            file=sys.stderr,
        )
        run_server(
            args.model,
            host=args.host,
            port=args.port,
            engine_type=args.engine,
            max_concurrent=args.max_concurrent,
        )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
