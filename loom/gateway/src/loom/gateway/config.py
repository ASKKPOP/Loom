"""Runtime configuration sourced from environment variables."""

from __future__ import annotations

import os


def _get(key: str, default: str) -> str:
    return os.environ.get(key, default).strip()


def bind_host() -> str:
    return _get("LOOM_BIND", "127.0.0.1")


def bind_port() -> int:
    return int(_get("LOOM_PORT", "8080"))


def vmlx_url() -> str:
    """Base URL of the vMLX backend (no trailing slash)."""
    return _get("LOOM_VMLX_URL", "http://127.0.0.1:8000").rstrip("/")


def log_level() -> str:
    return _get("LOOM_LOG_LEVEL", "info").lower()
