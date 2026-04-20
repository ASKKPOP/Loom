"""Smoke tests for the vmlx package skeleton."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile

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


def test_cli_serve_returns_zero() -> None:
    rc = cli.main(["serve", "some/model"])
    assert rc == 0


def test_cli_no_args_prints_help() -> None:
    rc = cli.main([])
    assert rc == 0
