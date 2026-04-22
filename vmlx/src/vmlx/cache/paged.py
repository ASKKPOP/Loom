"""PagedKVCacheManager — block-paged KV cache for Apple unified memory.

Algorithmic reference: vLLM PagedAttention (arXiv:2309.06180). The core idea
is to store per-sequence KV tensors in fixed-size blocks drawn from a shared
pool, so sequences of different lengths can share one underlying tensor
without padding to ``max_len``.

Apple unified memory is the reason this is a clean fit: CPU (the scheduler)
and GPU (the attention kernel) see the same bytes, so a block-table walk in
Python does not imply a host→device copy. The scheduler writes KV via
``mx.array`` indexed assignment, the attention path reads via ``mx.take``,
and the same buffer serves both. On a discrete-memory system this pattern
would cost a PCIe round-trip per allocation; here it costs nothing.

Block size. 16 tokens matches the vLLM default and gives good internal
fragmentation (worst-case waste per sequence is ``block_size - 1`` tokens).
For a typical head_dim=64, num_kv_heads=8, fp16 layout, each block holds
8 × 64 × 16 × 2 = 16 KiB per tensor (K or V) per layer — cache-line aligned
on Apple Silicon's 128-byte lines.

Per-layer state. Each (sequence, layer) pair owns its own block table and
length counter. In practice a transformer advances all layers in lockstep
within one forward pass; the per-layer tracking simply decouples them so
callers don't need to orchestrate a batched "commit" step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import mlx.core as mx


@dataclass(frozen=True)
class PagedCacheConfig:
    """Shape and dtype of the paged KV pool.

    ``num_blocks * block_size`` is the maximum number of *committed* KV
    tokens the cache can hold at once across every sequence **and every
    layer**. Choose ``num_blocks`` to cover
    ``num_layers * max_concurrent_seqs * ceil(worst_ctx_len / block_size)``.
    """

    num_blocks: int
    num_layers: int
    num_kv_heads: int
    head_dim: int
    block_size: int = 16
    dtype: str = "float16"

    def __post_init__(self) -> None:
        if self.num_blocks <= 0:
            raise ValueError(f"num_blocks must be positive, got {self.num_blocks}")
        if self.block_size <= 0:
            raise ValueError(f"block_size must be positive, got {self.block_size}")
        if self.num_layers <= 0:
            raise ValueError(f"num_layers must be positive, got {self.num_layers}")
        if self.num_kv_heads <= 0:
            raise ValueError(f"num_kv_heads must be positive, got {self.num_kv_heads}")
        if self.head_dim <= 0:
            raise ValueError(f"head_dim must be positive, got {self.head_dim}")


@dataclass
class _LayerSlot:
    blocks: list[int] = field(default_factory=list)
    length: int = 0  # logical tokens written to this layer


class PagedKVCacheManager:
    """Block-paged KV cache manager.

    Owns a pool of ``num_blocks`` blocks, each shaped
    ``(block_size, num_kv_heads, head_dim)``. Per layer, two tensors
    (K and V) share the pool's block axis. Sequences are addressed by a
    caller-supplied string id; each ``(seq_id, layer)`` pair has its own
    block table.

    Concurrency. This class is **not** thread-safe. The expected caller is
    the scheduler thread in :class:`vmlx.engine.BatchingEngine`, which is
    already the sole owner of KV state (see batching.py). If you need
    multi-threaded use, wrap with an external lock.
    """

    def __init__(self, config: PagedCacheConfig) -> None:
        import mlx.core as mx

        dtype = getattr(mx, config.dtype, None)
        if dtype is None:
            raise ValueError(f"unknown mx dtype {config.dtype!r}")

        self._config = config
        shape = (config.num_blocks, config.block_size, config.num_kv_heads, config.head_dim)
        self._k_cache: list[mx.array] = [
            mx.zeros(shape, dtype=dtype) for _ in range(config.num_layers)
        ]
        self._v_cache: list[mx.array] = [
            mx.zeros(shape, dtype=dtype) for _ in range(config.num_layers)
        ]
        # LIFO free-list: popping from the end is O(1) and keeps recently
        # freed blocks hot (helpful for locality).
        self._free: list[int] = list(range(config.num_blocks))
        # (seq_id, layer) → _LayerSlot
        self._slots: dict[tuple[str, int], _LayerSlot] = {}
        # seq_id → True (tracks which sequences are open)
        self._open: set[str] = set()

    # ─── shape / capacity ─────────────────────────────────────────────

    @property
    def config(self) -> PagedCacheConfig:
        return self._config

    @property
    def num_blocks(self) -> int:
        return self._config.num_blocks

    @property
    def block_size(self) -> int:
        return self._config.block_size

    @property
    def num_free_blocks(self) -> int:
        return len(self._free)

    @property
    def num_allocated_blocks(self) -> int:
        return self._config.num_blocks - len(self._free)

    # ─── sequence lifecycle ───────────────────────────────────────────

    def has_sequence(self, seq_id: str) -> bool:
        return seq_id in self._open

    def open_sequence(self, seq_id: str) -> None:
        """Register a new sequence. Raises if one already exists under this id."""
        if seq_id in self._open:
            raise ValueError(f"sequence {seq_id!r} already open")
        self._open.add(seq_id)
        for layer in range(self._config.num_layers):
            self._slots[(seq_id, layer)] = _LayerSlot()

    def free_sequence(self, seq_id: str) -> int:
        """Release the sequence's blocks back to the pool. Returns # blocks freed."""
        if seq_id not in self._open:
            return 0
        self._open.discard(seq_id)
        freed = 0
        for layer in range(self._config.num_layers):
            slot = self._slots.pop((seq_id, layer), None)
            if slot is None:
                continue
            for b in slot.blocks:
                self._free.append(b)
                freed += 1
        return freed

    def sequence_length(self, seq_id: str, layer: int = 0) -> int:
        """Tokens written to ``(seq_id, layer)``. Defaults to layer 0 since
        all layers advance in lockstep during normal transformer inference."""
        self._require_layer(layer)
        self._require_open(seq_id)
        return self._slots[(seq_id, layer)].length

    def block_table(self, seq_id: str, layer: int = 0) -> list[int]:
        """Return a copy of ``(seq_id, layer)``'s block ids in logical order."""
        self._require_layer(layer)
        self._require_open(seq_id)
        return list(self._slots[(seq_id, layer)].blocks)

    def active_sequence_ids(self) -> list[str]:
        return list(self._open)

    # ─── append / read ────────────────────────────────────────────────

    def append_kv(
        self,
        seq_id: str,
        layer: int,
        k: mx.array,
        v: mx.array,
    ) -> None:
        """Append ``T`` new KV tokens for ``(seq_id, layer)``.

        ``k`` and ``v`` must be shaped ``(T, num_kv_heads, head_dim)``. New
        blocks are allocated from the free pool as needed; raises
        :class:`MemoryError` if the pool is exhausted.
        """
        self._require_layer(layer)
        self._require_open(seq_id)
        slot = self._slots[(seq_id, layer)]

        t = k.shape[0]
        if v.shape[0] != t:
            raise ValueError(f"k/v must share axis 0, got k={k.shape} v={v.shape}")
        expected_tail = (self._config.num_kv_heads, self._config.head_dim)
        if tuple(k.shape[1:]) != expected_tail or tuple(v.shape[1:]) != expected_tail:
            raise ValueError(
                f"k/v tail shape must be {expected_tail}, got k={tuple(k.shape)} v={tuple(v.shape)}"
            )
        if t == 0:
            return

        block_size = self._config.block_size
        k_cache = self._k_cache[layer]
        v_cache = self._v_cache[layer]

        written = 0
        while written < t:
            block_pos = slot.length % block_size
            block_idx = slot.length // block_size
            if block_pos == 0 and block_idx >= len(slot.blocks):
                slot.blocks.append(self._alloc_block())
            block_id = slot.blocks[block_idx]
            take = min(block_size - block_pos, t - written)
            k_cache[block_id, block_pos : block_pos + take] = k[written : written + take]
            v_cache[block_id, block_pos : block_pos + take] = v[written : written + take]
            written += take
            slot.length += take

        # setitem mutates in place on current MLX, but reassignment makes the
        # contract explicit and guards against future API changes.
        self._k_cache[layer] = k_cache
        self._v_cache[layer] = v_cache

    def gather_kv(self, seq_id: str, layer: int) -> tuple[mx.array, mx.array]:
        """Return ``(K, V)`` as contiguous arrays of shape ``(L, num_kv_heads, head_dim)``.

        ``L`` is the layer's current sequence length. The returned arrays
        are fresh — they don't alias the pool — so the caller can feed
        them directly into SDPA without worrying about subsequent appends
        clobbering.
        """
        import mlx.core as mx

        self._require_layer(layer)
        self._require_open(seq_id)
        slot = self._slots[(seq_id, layer)]
        tail = (self._config.num_kv_heads, self._config.head_dim)
        if slot.length == 0:
            dtype = self._k_cache[layer].dtype
            empty = mx.zeros((0, *tail), dtype=dtype)
            return empty, empty

        block_ids = mx.array(slot.blocks, dtype=mx.int32)
        # (num_blocks_used, block_size, num_kv_heads, head_dim)
        k = mx.take(self._k_cache[layer], block_ids, axis=0)
        v = mx.take(self._v_cache[layer], block_ids, axis=0)
        flat_shape = (k.shape[0] * self._config.block_size, *tail)
        k = k.reshape(flat_shape)[: slot.length]
        v = v.reshape(flat_shape)[: slot.length]
        return k, v

    # ─── observability ────────────────────────────────────────────────

    def utilization(self) -> float:
        """Committed tokens / allocated token slots across all (seq, layer).

        Returns a value in ``[0, 1]``. This is the efficiency metric the
        paged design is meant to improve vs. a padded baseline: with block
        size ``B``, worst-case waste per (sequence, layer) is ``B - 1``
        tokens, so utilization tends to ``1 - (B - 1) / (2 * avg_len)``
        under uniform lengths (empirically >80% for ``avg_len >= 40``,
        ``B = 16``).
        """
        committed = sum(s.length for s in self._slots.values())
        allocated = sum(len(s.blocks) for s in self._slots.values())
        if allocated == 0:
            return 1.0
        return committed / (allocated * self._config.block_size)

    def padded_baseline_slots(self) -> int:
        """How many token slots a padded ``(n_seqs, max_len)`` layout would spend.

        Useful for benchmarks: compare total committed tokens against
        this to quantify savings vs. padding to the longest sequence.
        """
        if not self._open:
            return 0
        max_len = 0
        for seq_id in self._open:
            ln = self._slots[(seq_id, 0)].length
            if ln > max_len:
                max_len = ln
        return max_len * len(self._open) * self._config.num_layers

    # ─── internals ────────────────────────────────────────────────────

    def _alloc_block(self) -> int:
        if not self._free:
            raise MemoryError(
                f"paged cache exhausted: all {self._config.num_blocks} blocks in use"
            )
        return self._free.pop()

    def _require_layer(self, layer: int) -> None:
        if not 0 <= layer < self._config.num_layers:
            raise IndexError(
                f"layer {layer} out of range [0, {self._config.num_layers})"
            )

    def _require_open(self, seq_id: str) -> None:
        if seq_id not in self._open:
            raise KeyError(f"sequence {seq_id!r} not open; call open_sequence() first")
