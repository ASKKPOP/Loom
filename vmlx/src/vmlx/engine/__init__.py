"""Inference engines.

`SingleRequestEngine` is the reference baseline: one request at a time, no
batching, no paged cache. All later scheduler work benchmarks against it.
"""

from __future__ import annotations

from vmlx.engine.single import GenerationResult, SingleRequestEngine

__all__ = ["GenerationResult", "SingleRequestEngine"]
