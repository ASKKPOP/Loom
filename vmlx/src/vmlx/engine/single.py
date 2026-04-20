"""SingleRequestEngine — reference baseline inference engine.

One request at a time, no batching, no paged KV cache, no concurrency. Wraps
`mlx_lm.stream_generate` and surfaces tokens/sec, peak memory, and finish
reason as a `GenerationResult` dataclass.
"""

from __future__ import annotations

import gc
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mlx import nn
    from mlx_lm.tokenizer_utils import TokenizerWrapper


@dataclass(frozen=True)
class GenerationResult:
    """Outcome of a single `SingleRequestEngine.generate` call."""

    text: str
    prompt_tokens: int
    generation_tokens: int
    tokens_per_second: float
    peak_memory_mb: float
    duration_s: float
    finish_reason: str | None


class SingleRequestEngine:
    """Load an MLX model and run one generate() call at a time.

    Usage:
        engine = SingleRequestEngine("mlx-community/Qwen2.5-0.5B-Instruct-4bit")
        engine.load()
        result = engine.generate("Hello", max_tokens=50)
        engine.unload()
    """

    def __init__(self, model_id: str) -> None:
        self._model_id = model_id
        self._model: nn.Module | None = None
        self._tokenizer: TokenizerWrapper | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def load(self) -> None:
        from mlx_lm import load as mlx_load

        # mlx_lm.load returns (model, tokenizer) when return_config is unset/False;
        # the union type in the stub is wider so unpack via indexing.
        result = mlx_load(self._model_id)
        self._model = result[0]
        self._tokenizer = result[1]

    def unload(self) -> None:
        self._model = None
        self._tokenizer = None
        gc.collect()

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 50,
        apply_chat_template: bool = True,
        **sampler_kwargs: Any,
    ) -> GenerationResult:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError(
                "SingleRequestEngine.generate called before load(); "
                "call engine.load() first"
            )
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens!r}")

        from mlx_lm import stream_generate

        tokenizer = self._tokenizer

        if apply_chat_template and hasattr(tokenizer, "apply_chat_template"):
            token_input = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                add_generation_prompt=True,
            )
        else:
            token_input = prompt

        pieces: list[str] = []
        last: Any = None
        start = time.perf_counter()
        for response in stream_generate(
            self._model,
            tokenizer,
            token_input,
            max_tokens=max_tokens,
            **sampler_kwargs,
        ):
            pieces.append(response.text)
            last = response
        duration = time.perf_counter() - start

        if last is None:
            return GenerationResult(
                text="",
                prompt_tokens=0,
                generation_tokens=0,
                tokens_per_second=0.0,
                peak_memory_mb=0.0,
                duration_s=duration,
                finish_reason="empty",
            )

        return GenerationResult(
            text="".join(pieces),
            prompt_tokens=int(last.prompt_tokens),
            generation_tokens=int(last.generation_tokens),
            tokens_per_second=float(last.generation_tps),
            peak_memory_mb=float(last.peak_memory),
            duration_s=duration,
            finish_reason=last.finish_reason,
        )
