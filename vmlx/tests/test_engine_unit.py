"""Unit tests for SingleRequestEngine — no model load, no Metal required."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vmlx.engine import GenerationResult, SingleRequestEngine


def test_engine_construct_without_load() -> None:
    engine = SingleRequestEngine("some/model-id")
    assert engine.model_id == "some/model-id"
    assert engine.is_loaded is False


def test_generate_before_load_raises() -> None:
    engine = SingleRequestEngine("some/model-id")
    with pytest.raises(RuntimeError, match="before load"):
        engine.generate("hi")


def test_generate_rejects_non_positive_max_tokens() -> None:
    engine = SingleRequestEngine("some/model-id")
    # unload state makes the load check fire first, so first mimic loaded
    # state by setting private attrs (unit test of input validation only).
    engine._model = object()  # type: ignore[assignment]
    engine._tokenizer = object()  # type: ignore[assignment]
    with pytest.raises(ValueError, match="max_tokens must be positive"):
        engine.generate("hi", max_tokens=0)
    with pytest.raises(ValueError, match="max_tokens must be positive"):
        engine.generate("hi", max_tokens=-1)


def test_unload_clears_state() -> None:
    engine = SingleRequestEngine("some/model-id")
    engine._model = object()  # type: ignore[assignment]
    engine._tokenizer = object()  # type: ignore[assignment]
    assert engine.is_loaded is True
    engine.unload()
    assert engine.is_loaded is False


def test_generation_result_is_frozen() -> None:
    result = GenerationResult(
        text="hi",
        prompt_tokens=1,
        generation_tokens=1,
        tokens_per_second=10.0,
        peak_memory_mb=100.0,
        duration_s=0.1,
        finish_reason="stop",
    )
    with pytest.raises(FrozenInstanceError):
        result.text = "mutated"  # type: ignore[misc]
