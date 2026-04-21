"""Engine registry: map `--engine <name>` to an engine factory.

Adding a new engine is a one-line change here. Engines must satisfy
:class:`EngineProtocol` (structurally).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from vmlx.engine import BatchingEngine, GenerationResult, SingleRequestEngine


@runtime_checkable
class EngineProtocol(Protocol):
    """Minimum interface the benchmark harness needs from any engine."""

    @property
    def model_id(self) -> str: ...

    def load(self) -> None: ...

    def unload(self) -> None: ...

    def generate(self, prompt: str, *, max_tokens: int = ...) -> GenerationResult: ...


EngineFactory = Callable[[str], EngineProtocol]


ENGINES: dict[str, EngineFactory] = {
    "single": lambda model_id: SingleRequestEngine(model_id),
    "batching": lambda model_id: BatchingEngine(model_id),
}


def available_engines() -> list[str]:
    return sorted(ENGINES.keys())


def build_engine(name: str, model_id: str) -> EngineProtocol:
    if name not in ENGINES:
        raise ValueError(
            f"unknown engine {name!r}; available: {available_engines()}"
        )
    return ENGINES[name](model_id)
