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
        help="Serve an MLX model over HTTP (not yet implemented)",
    )
    serve.add_argument("model", help="Model id (e.g. mlx-community/...)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        print(
            f"vmlx serve: model={args.model} host={args.host} port={args.port}",
            file=sys.stderr,
        )
        print(
            "(not yet implemented — serving engine lands in vmlx-004)",
            file=sys.stderr,
        )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
