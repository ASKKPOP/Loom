"""Inference engines.

`SingleRequestEngine` is the reference baseline: one request at a time, no
batching, no paged cache. All later scheduler work benchmarks against it.
"""

from __future__ import annotations

from vmlx.engine.batching import BatchingEngine
from vmlx.engine.single import (
    GenerationResult,
    Message,
    SingleRequestEngine,
    StreamChunk,
)

__all__ = [
    "BatchingEngine",
    "GenerationResult",
    "Message",
    "SingleRequestEngine",
    "StreamChunk",
]
