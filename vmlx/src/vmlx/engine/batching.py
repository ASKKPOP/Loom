"""BatchingEngine — continuous-batched inference via mlx_lm.BatchGenerator.

A single scheduler thread owns the underlying ``BatchGenerator`` and is the
sole caller of ``insert()`` / ``next_generated()`` / ``remove()``. Request
submissions from other threads go through a thread-safe queue; each request
receives a dedicated output queue which the scheduler writes into.

Contract matches :class:`vmlx.engine.SingleRequestEngine`: same
``GenerationResult`` / ``StreamChunk`` types, same ``ServerEngine`` protocol
shape, so the FastAPI server, benchmark harness, and tests treat both
engines interchangeably.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from vmlx.engine.single import GenerationResult, Message, StreamChunk

if TYPE_CHECKING:
    from mlx import nn
    from mlx_lm.tokenizer_utils import TokenizerWrapper


_SHUTDOWN = object()
_SCHEDULER_IDLE_TIMEOUT_S = 0.05


@dataclass
class _Request:
    """A single in-flight request, tracked by the scheduler thread."""

    prompt_token_ids: list[int]
    max_tokens: int
    output_queue: queue.Queue[StreamChunk | BaseException] = field(
        default_factory=queue.Queue
    )
    # Populated by the scheduler when it has registered the request with
    # BatchGenerator and has a uid.
    uid_ready: threading.Event = field(default_factory=threading.Event)
    uid: int = -1
    # Filled incrementally by the scheduler:
    detokenizer: Any = None
    start_perf_counter: float = 0.0
    first_token_latency_ms: float = 0.0
    token_count: int = 0


class BatchingEngine:
    """Continuous-batched engine for concurrent requests on one Mac."""

    def __init__(
        self,
        model_id: str,
        *,
        max_concurrent: int = 32,
        scheduler_idle_timeout_s: float = _SCHEDULER_IDLE_TIMEOUT_S,
    ) -> None:
        self._model_id = model_id
        self._max_concurrent = max_concurrent
        self._idle_timeout = scheduler_idle_timeout_s

        self._model: nn.Module | None = None
        self._tokenizer: TokenizerWrapper | None = None
        self._batch_gen: Any = None

        self._pending: queue.Queue[_Request | object] = queue.Queue()
        self._uid_to_request: dict[int, _Request] = {}
        self._lock = threading.Lock()

        self._scheduler_thread: threading.Thread | None = None
        self._running = False

    # ─── public surface (matches ServerEngine protocol) ────────────

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def is_loaded(self) -> bool:
        return self._scheduler_thread is not None and self._scheduler_thread.is_alive()

    def load(self) -> None:
        from mlx_lm import load as mlx_load
        from mlx_lm.generate import BatchGenerator

        result = mlx_load(self._model_id)
        self._model = result[0]
        self._tokenizer = result[1]

        eos_ids = _eos_token_ids(self._tokenizer)
        stop_tokens = [[t] for t in eos_ids] if eos_ids else None

        self._batch_gen = BatchGenerator(
            self._model,
            stop_tokens=stop_tokens,
            completion_batch_size=self._max_concurrent,
        )

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="vmlx-batching-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()

    def unload(self) -> None:
        if self._scheduler_thread is None:
            return
        self._running = False
        self._pending.put(_SHUTDOWN)
        self._scheduler_thread.join(timeout=10.0)
        self._scheduler_thread = None
        if self._batch_gen is not None:
            import contextlib

            with contextlib.suppress(Exception):
                self._batch_gen.close()
            self._batch_gen = None
        self._model = None
        self._tokenizer = None
        self._uid_to_request.clear()

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 50,
    ) -> GenerationResult:
        """One-shot generation. Buffers all stream output and returns aggregate."""
        pieces: list[str] = []
        final: StreamChunk | None = None
        start = time.perf_counter()
        for chunk in self.stream_generate(prompt, max_tokens=max_tokens):
            if chunk.text:
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
    ) -> Iterator[StreamChunk]:
        """Stream incremental chunks. Thread-safe: call from many threads."""
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens!r}")
        if not self.is_loaded:
            raise RuntimeError(
                "BatchingEngine called before load(); call engine.load() first"
            )

        tokenizer = self._tokenizer
        assert tokenizer is not None
        prompt_token_ids = _tokenize_messages(tokenizer, messages)

        req = _Request(
            prompt_token_ids=prompt_token_ids,
            max_tokens=max_tokens,
        )
        self._pending.put(req)

        # Drain chunks from the scheduler.
        while True:
            item = req.output_queue.get()
            if isinstance(item, BaseException):
                raise item
            yield item
            if item.is_final:
                return

    # ─── internals ─────────────────────────────────────────────────

    def _scheduler_loop(self) -> None:
        try:
            while self._running:
                self._drain_pending()
                if not self._uid_to_request:
                    # No active work — block briefly on the pending queue.
                    try:
                        first = self._pending.get(timeout=self._idle_timeout)
                    except queue.Empty:
                        continue
                    if first is _SHUTDOWN:
                        return
                    assert isinstance(first, _Request)
                    self._insert_one(first)
                    continue

                # Step the batch.
                try:
                    responses = self._batch_gen.next_generated()
                except Exception as exc:  # propagate error to all active reqs
                    self._fail_all(exc)
                    return

                self._route_responses(responses)
        finally:
            self._running = False
            self._fail_all(
                RuntimeError("vmlx: batching scheduler stopped")
                if self._uid_to_request
                else None
            )

    def _drain_pending(self) -> None:
        while True:
            try:
                item = self._pending.get_nowait()
            except queue.Empty:
                return
            if item is _SHUTDOWN:
                self._running = False
                return
            assert isinstance(item, _Request)
            self._insert_one(item)

    def _insert_one(self, req: _Request) -> None:
        from mlx_lm.tokenizer_utils import NaiveStreamingDetokenizer

        assert self._batch_gen is not None and self._tokenizer is not None
        req.detokenizer = NaiveStreamingDetokenizer(self._tokenizer)
        req.start_perf_counter = time.perf_counter()
        uids = self._batch_gen.insert(
            [req.prompt_token_ids],
            max_tokens=[req.max_tokens],
        )
        req.uid = int(uids[0])
        with self._lock:
            self._uid_to_request[req.uid] = req
        req.uid_ready.set()

    def _route_responses(self, responses: list[Any]) -> None:
        finished: list[int] = []
        for r in responses:
            req = self._uid_to_request.get(r.uid)
            if req is None:
                continue
            req.token_count += 1
            if req.token_count == 1:
                req.first_token_latency_ms = (
                    time.perf_counter() - req.start_perf_counter
                ) * 1000.0
            req.detokenizer.add_token(int(r.token))
            segment = req.detokenizer.last_segment
            if segment or r.finish_reason is None:
                req.output_queue.put(
                    StreamChunk(
                        text=segment,
                        is_final=False,
                        finish_reason=r.finish_reason,
                    )
                )
            if r.finish_reason is not None:
                # Flush remaining detokenizer state.
                req.detokenizer.finalize()
                tail = req.detokenizer.last_segment
                if tail:
                    req.output_queue.put(
                        StreamChunk(text=tail, is_final=False, finish_reason=None)
                    )
                duration = time.perf_counter() - req.start_perf_counter
                tps = req.token_count / duration if duration > 0 else 0.0
                req.output_queue.put(
                    StreamChunk(
                        text="",
                        is_final=True,
                        prompt_tokens=len(req.prompt_token_ids),
                        generation_tokens=req.token_count,
                        tokens_per_second=tps,
                        ttft_ms=req.first_token_latency_ms,
                        peak_memory_mb=_peak_memory_mb(),
                        finish_reason=r.finish_reason,
                    )
                )
                finished.append(r.uid)

        if finished:
            self._batch_gen.remove(finished)
            with self._lock:
                for uid in finished:
                    self._uid_to_request.pop(uid, None)

    def _fail_all(self, exc: BaseException | None) -> None:
        if exc is None:
            return
        with self._lock:
            reqs = list(self._uid_to_request.values())
            self._uid_to_request.clear()
        for req in reqs:
            req.output_queue.put(exc)


# ─── helpers ───────────────────────────────────────────────────────


def _peak_memory_mb() -> float:
    try:
        import mlx.core as mx

        return float(mx.get_peak_memory()) / 1e6
    except Exception:
        return 0.0


def _eos_token_ids(tokenizer: Any) -> list[int]:
    ids: list[int] = []
    eos = getattr(tokenizer, "eos_token_id", None)
    if isinstance(eos, int):
        ids.append(eos)
    elif isinstance(eos, list):
        ids.extend(int(x) for x in eos if isinstance(x, int))
    extra = getattr(tokenizer, "eos_token_ids", None)
    if isinstance(extra, list):
        ids.extend(int(x) for x in extra if isinstance(x, int))
    # De-dupe while preserving order.
    seen: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i not in seen:
            out.append(i)
            seen.add(i)
    return out


def _tokenize_messages(
    tokenizer: Any, messages: Sequence[Message] | str
) -> list[int]:
    if isinstance(messages, str):
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": messages}],
            add_generation_prompt=True,
        )
    else:
        rendered = tokenizer.apply_chat_template(
            list(messages),
            add_generation_prompt=True,
        )
    # apply_chat_template may return a list[int] directly (mlx-lm wrapper) or
    # a string that still needs encoding (pure HF tokenizer). Handle both.
    if isinstance(rendered, list):
        return [int(x) for x in rendered]
    if isinstance(rendered, str):
        return list(tokenizer.encode(rendered))
    raise TypeError(
        f"apply_chat_template returned unsupported type {type(rendered).__name__}"
    )
