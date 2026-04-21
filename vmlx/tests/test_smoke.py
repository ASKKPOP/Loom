"""Smoke tests for the vmlx package skeleton."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile

import pytest

import vmlx
from vmlx import cli

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+].+)?$")


def test_version_is_semver() -> None:
    assert SEMVER_RE.match(vmlx.__version__), (
        f"vmlx.__version__={vmlx.__version__!r} is not a valid semver string"
    )


def test_version_exported() -> None:
    assert "__version__" in vmlx.__all__


def test_cli_parser_has_serve_command() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["serve", "some/model"])
    assert args.command == "serve"
    assert args.model == "some/model"
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_cli_version_flag() -> None:
    # Run from a neutral cwd so the `vmlx/` source directory (when pytest
    # runs from inside it) does not shadow the installed package.
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-m", "vmlx.cli", "--version"],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmpdir,
        )
    assert result.returncode == 0, result.stderr
    assert vmlx.__version__ in result.stdout


def test_cli_serve_invokes_run_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """`vmlx serve <model>` wires through to api.server.run_server.

    We don't actually want to bind a socket or load a model here — swap
    run_server for a spy and assert it's called with the parsed args.
    """
    calls: list[tuple[str, str, int]] = []

    def fake_run_server(model: str, *, host: str, port: int) -> None:
        calls.append((model, host, port))

    monkeypatch.setattr("vmlx.api.server.run_server", fake_run_server)
    rc = cli.main(["serve", "some/model", "--port", "9999"])
    assert rc == 0
    assert calls == [("some/model", "127.0.0.1", 9999)]


def test_cli_no_args_prints_help() -> None:
    rc = cli.main([])
    assert rc == 0
