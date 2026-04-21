"""SingleRequestEngine — reference baseline inference engine.

One request at a time, no batching, no paged KV cache, no concurrency. Wraps
`mlx_lm.stream_generate` and surfaces tokens/sec, peak memory, and finish
reason as a `GenerationResult` dataclass.
"""

from __future__ import annotations

import gc
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mlx import nn
    from mlx_lm.tokenizer_utils import TokenizerWrapper


Message = dict[str, str]


@dataclass(frozen=True)
class GenerationResult:
    """Outcome of a single `SingleRequestEngine.generate` call."""

    text: str
    prompt_tokens: int
    generation_tokens: int
    tokens_per_second: float
    ttft_ms: float
    peak_memory_mb: float
    duration_s: float
    finish_reason: str | None


@dataclass(frozen=True)
class StreamChunk:
    """A single delta from an engine's ``stream_generate``.

    ``text`` is the incremental piece produced this step; concatenating every
    non-final chunk's text yields the full output. The final chunk has
    ``is_final=True`` and carries the authoritative counters (including
    ``ttft_ms``).
    """

    text: str
    is_final: bool
    prompt_tokens: int = 0
    generation_tokens: int = 0
    tokens_per_second: float = 0.0
    ttft_ms: float = 0.0
    peak_memory_mb: float = 0.0
    finish_reason: str | None = None


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
        self._first_token_latency_ms = 0.0

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
        """One-shot generation, buffered. Returns the complete result."""
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens!r}")
        self._require_loaded()

        pieces: list[str] = []
        final: StreamChunk | None = None
        start = time.perf_counter()
        for chunk in self._stream(
            self._to_prompt(prompt, apply_chat_template=apply_chat_template),
            max_tokens=max_tokens,
            start=start,
            **sampler_kwargs,
        ):
            pieces.append(chunk.text)
            if chunk.is_final:
                final = chunk
        duration = time.perf_counter() - start

        if final is None:
            return GenerationResult(
                text="".join(pieces),
                prompt_tokens=0,
                generation_tokens=0,
                tokens_per_second=0.0,
                ttft_ms=0.0,
                peak_memory_mb=0.0,
                duration_s=duration,
                finish_reason="empty",
            )

        return GenerationResult(
            text="".join(pieces),
            prompt_tokens=final.prompt_tokens,
            generation_tokens=final.generation_tokens,
            tokens_per_second=final.tokens_per_second,
            ttft_ms=final.ttft_ms,
            peak_memory_mb=final.peak_memory_mb,
            duration_s=duration,
            finish_reason=final.finish_reason,
        )

    def stream_generate(
        self,
        messages: Sequence[Message] | str,
        *,
        max_tokens: int = 50,
        **sampler_kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """Stream incremental output chunks. Final chunk has is_final=True.

        `messages` may be an OpenAI-style list of ``{"role", "content"}``
        dicts (chat template applied) or a raw pre-formatted prompt string.
        """
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens!r}")
        self._require_loaded()
        yield from self._stream(
            self._messages_to_prompt(messages),
            max_tokens=max_tokens,
            start=time.perf_counter(),
            **sampler_kwargs,
        )

    # ─── internals ─────────────────────────────────────────────────

    def _require_loaded(self) -> None:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError(
                "engine called before load(); call engine.load() first"
            )

    def _to_prompt(self, prompt: str, *, apply_chat_template: bool) -> Any:
        tokenizer = self._tokenizer
        assert tokenizer is not None
        if apply_chat_template and hasattr(tokenizer, "apply_chat_template"):
            return tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                add_generation_prompt=True,
            )
        return prompt

    def _messages_to_prompt(self, messages: Sequence[Message] | str) -> Any:
        if isinstance(messages, str):
            return self._to_prompt(messages, apply_chat_template=True)
        tokenizer = self._tokenizer
        assert tokenizer is not None
        return tokenizer.apply_chat_template(
            list(messages),
            add_generation_prompt=True,
        )

    def _stream(
        self,
        token_input: Any,
        *,
        max_tokens: int,
        start: float,
        **sampler_kwargs: Any,
    ) -> Iterator[StreamChunk]:
        from mlx_lm import stream_generate as _mlx_stream

        # _require_loaded (called by public methods) narrows; assert here for mypy.
        model = self._model
        tokenizer = self._tokenizer
        assert model is not None and tokenizer is not None

        seen_first = False
        last: Any = None
        for response in _mlx_stream(
            model,
            tokenizer,
            token_input,
            max_tokens=max_tokens,
            **sampler_kwargs,
        ):
            if not seen_first:
                self._first_token_latency_ms = (
                    time.perf_counter() - start
                ) * 1000.0
                seen_first = True
            last = response
            # Non-final chunk: only the incremental text matters here.
            yield StreamChunk(
                text=response.text,
                is_final=False,
                finish_reason=response.finish_reason,
            )

        if last is not None:
            yield StreamChunk(
                text="",
                is_final=True,
                prompt_tokens=int(last.prompt_tokens),
                generation_tokens=int(last.generation_tokens),
                tokens_per_second=float(last.generation_tps),
                ttft_ms=self._first_token_latency_ms,
                peak_memory_mb=float(last.peak_memory),
                finish_reason=last.finish_reason,
            )
