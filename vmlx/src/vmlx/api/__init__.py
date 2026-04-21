"""HTTP API surfaces for vMLX.

Currently exposes an OpenAI-compatible subset via :mod:`vmlx.api.server`.
Anthropic-compatible endpoints will live in a sibling module later.
"""

from __future__ import annotations

from vmlx.api.server import create_app

__all__ = ["create_app"]
