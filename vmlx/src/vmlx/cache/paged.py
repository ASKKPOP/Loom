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

Block table layout. Each sequence owns a **single block table shared
across layers**. A block id indexes into every layer's (K, V) tensors at
the same position; different layers hold different data at the same
block id. This matches vLLM's layout and enables prefix caching (a
prefix's block ids are meaningful across all layers, not just one).

The lockstep invariant. In real transformer inference all layers advance
by the same number of tokens per forward pass. ``append_kv`` enforces
this: the sequence length advances only when ``layer == 0`` is called,
and subsequent layers for the same step must be called with the same
``T`` (write into positions reserved by layer 0's call).
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
    tokens the cache can hold at once across every sequence. Blocks are
    shared across layers (one block id indexes the same slot in every
    layer's tensor), so total bytes = ``2 × num_layers × num_blocks ×
    block_size × num_kv_heads × head_dim × sizeof(dtype)``.
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
class _SeqSlot:
    # Block ids in logical order. Shared across all layers.
    blocks: list[int] = field(default_factory=list)
    # Logical tokens written (advances once per step, not once per layer).
    length: int = 0


class PagedKVCacheManager:
    """Block-paged KV cache manager with shared-per-sequence block tables.

    Owns a pool of ``num_blocks`` blocks. Per layer, two tensors (K and V)
    share the pool's block axis: ``(num_blocks, block_size, num_kv_heads,
    head_dim)``. A sequence's block table is shared across layers; layers
    differ only in the data stored at each block.

    Concurrency. This class is **not** thread-safe. The expected caller is
    a single scheduler thread that owns all KV state (see the
    :class:`vmlx.engine.BatchingEngine` design). Wrap with a lock if you
    need multi-threaded use.
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
        # Per-block refcount. A block is in ``self._free`` iff its refcount is 0.
        # Refcount > 1 means the block is shared (e.g. a prefix block adopted
        # by multiple sequences, or retained by a PrefixCache).
        self._refcount: dict[int, int] = dict.fromkeys(range(config.num_blocks), 0)
        # seq_id → _SeqSlot (one slot per sequence, shared across layers).
        self._slots: dict[str, _SeqSlot] = {}
        # Tracks per-step write count per layer — lets us verify lockstep
        # usage and reject an append with the wrong T after layer 0 reserved.
        # Key: seq_id; value: (expected_t, layers_seen_this_step).
        self._step_trace: dict[str, tuple[int, set[int]]] = {}

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
        return seq_id in self._slots

    def open_sequence(self, seq_id: str) -> None:
        """Register a new sequence. Raises if one already exists under this id."""
        if seq_id in self._slots:
            raise ValueError(f"sequence {seq_id!r} already open")
        self._slots[seq_id] = _SeqSlot()

    def free_sequence(self, seq_id: str) -> int:
        """Release the sequence's refs to its blocks. Returns # blocks returned
        to the free-list (blocks whose refcount hit 0 after this release).

        A block with refcount > 1 (shared with a PrefixCache or another
        sequence) stays allocated; only its refcount is decremented.
        """
        slot = self._slots.pop(seq_id, None)
        if slot is None:
            return 0
        self._step_trace.pop(seq_id, None)
        returned = 0
        for b in slot.blocks:
            self._refcount[b] -= 1
            if self._refcount[b] == 0:
                self._free.append(b)
                returned += 1
            elif self._refcount[b] < 0:
                raise RuntimeError(
                    f"block {b} refcount went negative during free_sequence({seq_id!r}); "
                    "this indicates an unbalanced adopt/free pair"
                )
        return returned

    def sequence_length(self, seq_id: str) -> int:
        """Tokens logically written to the sequence (shared across all layers)."""
        self._require_open(seq_id)
        return self._slots[seq_id].length

    def block_table(self, seq_id: str) -> list[int]:
        """Return a copy of the sequence's block ids in logical order.

        Shared across all layers: each block id indexes into every layer's
        (K, V) tensors at the same slot.
        """
        self._require_open(seq_id)
        return list(self._slots[seq_id].blocks)

    def active_sequence_ids(self) -> list[str]:
        return list(self._slots.keys())

    # ─── append / read ────────────────────────────────────────────────

    def append_kv(
        self,
        seq_id: str,
        layer: int,
        k: mx.array,
        v: mx.array,
    ) -> None:
        """Append ``T`` new KV tokens for ``seq_id`` at ``layer``.

        Lockstep contract: within one forward pass, call with ``layer == 0``
        **first** (allocates blocks and advances the sequence length),
        then ``layer == 1, 2, ...`` with the same ``T`` (writes into the
        positions reserved by layer 0). Calling layers out of order or with
        mismatched ``T`` raises.

        ``k`` and ``v`` must be shaped ``(T, num_kv_heads, head_dim)``. New
        blocks are allocated from the free pool as needed on the layer-0
        call; raises :class:`MemoryError` if the pool is exhausted.
        """
        self._require_layer(layer)
        self._require_open(seq_id)
        slot = self._slots[seq_id]

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

        if layer == 0:
            # Layer 0 reserves blocks for [slot.length, slot.length + t) and
            # advances the logical length. Later layers in this step write
            # into those positions without advancing.
            write_start = slot.length
            while (slot.length + t - 1) // block_size >= len(slot.blocks):
                slot.blocks.append(self._alloc_block())
            slot.length += t
            self._step_trace[seq_id] = (t, {0})
        else:
            # Verify lockstep with layer 0.
            trace = self._step_trace.get(seq_id)
            if trace is None:
                raise RuntimeError(
                    f"append_kv({seq_id!r}, layer={layer}) called before layer 0 of this step; "
                    "layers must be written in order 0, 1, ..., N-1 each forward pass"
                )
            expected_t, seen = trace
            if t != expected_t:
                raise ValueError(
                    f"lockstep violation: layer 0 wrote {expected_t} tokens this step, "
                    f"layer {layer} wrote {t}"
                )
            if layer in seen:
                raise RuntimeError(
                    f"layer {layer} already written this step for sequence {seq_id!r}"
                )
            seen.add(layer)
            # Reconstruct write_start from the committed length.
            write_start = slot.length - t

        k_cache = self._k_cache[layer]
        v_cache = self._v_cache[layer]

        pos = write_start
        written = 0
        while written < t:
            block_pos = pos % block_size
            block_idx = pos // block_size
            block_id = slot.blocks[block_idx]
            take = min(block_size - block_pos, t - written)
            k_cache[block_id, block_pos : block_pos + take] = k[written : written + take]
            v_cache[block_id, block_pos : block_pos + take] = v[written : written + take]
            written += take
            pos += take

        # Reassignment preserves the contract explicitly (setitem mutates in
        # place on current MLX, but this guards against future API changes).
        self._k_cache[layer] = k_cache
        self._v_cache[layer] = v_cache

    def gather_kv(self, seq_id: str, layer: int) -> tuple[mx.array, mx.array]:
        """Return ``(K, V)`` as contiguous arrays of shape ``(L, num_kv_heads, head_dim)``.

        ``L`` is the sequence's current length. The returned arrays are
        fresh — they don't alias the pool — so the caller can feed them
        directly into SDPA without worrying about subsequent appends
        clobbering.
        """
        import mlx.core as mx

        self._require_layer(layer)
        self._require_open(seq_id)
        slot = self._slots[seq_id]
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

    # ─── prefix / refcount ────────────────────────────────────────────

    def adopt_prefix(
        self,
        seq_id: str,
        block_ids: list[int],
        num_tokens: int,
    ) -> None:
        """Attach pre-populated prefix blocks to ``seq_id`` (shared across layers).

        ``block_ids`` must hold valid K/V data for ``num_tokens`` tokens at
        every layer; each block's refcount is incremented once (not per
        layer — the block table itself is shared). The sequence must have
        no tokens written yet.
        """
        self._require_open(seq_id)
        slot = self._slots[seq_id]
        if slot.length != 0:
            raise RuntimeError(
                f"cannot adopt prefix for {seq_id!r}: sequence already has "
                f"{slot.length} tokens written"
            )
        expected_blocks = (num_tokens + self._config.block_size - 1) // self._config.block_size
        if len(block_ids) != expected_blocks:
            raise ValueError(
                f"expected {expected_blocks} blocks for {num_tokens} tokens "
                f"(block_size={self._config.block_size}), got {len(block_ids)}"
            )
        self.incref_blocks(block_ids)
        slot.blocks.extend(block_ids)
        slot.length = num_tokens

    def incref_blocks(self, block_ids: list[int]) -> None:
        """Increment the refcount of each block.

        Used by :class:`PrefixCache` when retaining blocks across sequence
        lifetimes, and by :meth:`adopt_prefix` when a new sequence adopts
        already-allocated prefix blocks.
        """
        for b in block_ids:
            if b not in self._refcount:
                raise ValueError(f"block {b} not in pool")
            if self._refcount[b] == 0:
                raise RuntimeError(
                    f"cannot incref block {b}: it is on the free-list "
                    "(refcount==0 means unowned)"
                )
            self._refcount[b] += 1

    def decref_blocks(self, block_ids: list[int]) -> int:
        """Decrement the refcount of each block; return # returned to free-list."""
        returned = 0
        for b in block_ids:
            if b not in self._refcount:
                raise ValueError(f"block {b} not in pool")
            if self._refcount[b] <= 0:
                raise RuntimeError(
                    f"cannot decref block {b}: refcount already {self._refcount[b]}"
                )
            self._refcount[b] -= 1
            if self._refcount[b] == 0:
                self._free.append(b)
                returned += 1
        return returned

    def refcount(self, block_id: int) -> int:
        """Return the refcount of a block. 0 means free."""
        return self._refcount[block_id]

    # ─── observability ────────────────────────────────────────────────

    def utilization(self) -> float:
        """Committed tokens / allocated token slots.

        Returns a value in ``[0, 1]``. This is the efficiency metric the
        paged design is meant to improve vs. a padded baseline: with block
        size ``B``, worst-case waste per sequence is ``B - 1`` tokens, so
        utilization tends to ``1 - (B - 1) / (2 * avg_len)`` under uniform
        lengths (empirically >80% for ``avg_len >= 40``, ``B = 16``).
        """
        committed = sum(s.length for s in self._slots.values())
        allocated = sum(len(s.blocks) for s in self._slots.values())
        if allocated == 0:
            return 1.0
        return committed / (allocated * self._config.block_size)

    def padded_baseline_slots(self) -> int:
        """Token slots a padded ``(n_seqs, max_len)`` layout would spend
        across every layer. Useful to quantify savings vs padding."""
        if not self._slots:
            return 0
        max_len = max(s.length for s in self._slots.values())
        return max_len * len(self._slots) * self._config.num_layers

    # ─── internals ────────────────────────────────────────────────────

    def _alloc_block(self) -> int:
        if not self._free:
            raise MemoryError(
                f"paged cache exhausted: all {self._config.num_blocks} blocks in use"
            )
        b = self._free.pop()
        self._refcount[b] = 1
        return b

    def _require_layer(self, layer: int) -> None:
        if not 0 <= layer < self._config.num_layers:
            raise IndexError(
                f"layer {layer} out of range [0, {self._config.num_layers})"
            )

    def _require_open(self, seq_id: str) -> None:
        if seq_id not in self._slots:
            raise KeyError(f"sequence {seq_id!r} not open; call open_sequence() first")
