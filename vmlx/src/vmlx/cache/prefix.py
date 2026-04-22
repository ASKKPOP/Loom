"""PrefixCache — content-addressed prefix reuse for the paged KV cache.

Token id sequences are hashed block-by-block (aligned to ``block_size``):
each block's hash = ``hash(parent_hash, tuple(token_ids_in_block))``. This
hash-chain design gives O(1)-per-block longest-common-prefix matching:
walk the chain and stop at the first miss.

Entries are refcounted in the coupled :class:`PagedKVCacheManager`. The
cache itself holds +1 per entry, so blocks can't be reclaimed by the pool
while still cached. When the cache evicts (LRU) or is cleared, it
decrements; blocks whose refcount hits 0 return to the free-list.

Hash collisions. Python's built-in ``hash()`` is cryptographically weak
but fine for an in-process cache. Every lookup additionally verifies the
stored ``token_ids`` match the query, so a collision yields a miss, not a
wrong-content hit.

Reference: vLLM automatic prefix caching, described in the PagedAttention
paper (arXiv:2309.06180 §5) and implemented in
``vllm/core/block_manager_v1.py``.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vmlx.cache.paged import PagedKVCacheManager


@dataclass(frozen=True)
class PrefixCacheStats:
    """Aggregate counters for ``PrefixCache``.

    ``hit_rate`` is ``hits / (hits + misses)`` if any lookups have occurred,
    else ``0.0``. A "hit" is any lookup that matched at least one block —
    partial hits (some blocks matched, some not) still count as hits.
    """

    lookups: int
    hits: int
    misses: int
    hit_rate: float
    cached_blocks: int


@dataclass
class _PrefixEntry:
    token_ids: tuple[int, ...]
    parent_hash: int
    block_id: int


class PrefixCache:
    """Block-granularity prefix cache with LRU eviction.

    Not thread-safe. Coupled to exactly one :class:`PagedKVCacheManager`;
    the cache calls the manager's ``incref_blocks`` / ``decref_blocks`` to
    keep refcounts accurate.
    """

    def __init__(
        self,
        manager: PagedKVCacheManager,
        *,
        max_entries: int | None = None,
    ) -> None:
        if max_entries is not None and max_entries <= 0:
            raise ValueError(f"max_entries must be positive or None, got {max_entries!r}")
        self._manager = manager
        self._block_size = manager.block_size
        # OrderedDict for LRU: move_to_end on access, popitem(last=False) for oldest.
        self._entries: OrderedDict[int, _PrefixEntry] = OrderedDict()
        self._max_entries = max_entries
        self._lookups = 0
        self._hits = 0
        self._misses = 0

    # ─── lookup / insert / clear ──────────────────────────────────────

    def lookup(self, token_ids: Sequence[int]) -> tuple[list[int], int]:
        """Return ``(block_ids, num_tokens_matched)`` for the longest prefix hit.

        Only block-aligned prefixes count. For ``len(token_ids) == L``
        tokens with block size ``B``, at most ``L // B`` blocks can match —
        the trailing ``L % B`` tokens never participate in caching.
        """
        self._lookups += 1
        n_blocks_available = len(token_ids) // self._block_size
        matched: list[int] = []
        parent_hash = 0
        for i in range(n_blocks_available):
            tokens = tuple(
                token_ids[i * self._block_size : (i + 1) * self._block_size]
            )
            h = hash((parent_hash, tokens))
            entry = self._entries.get(h)
            if (
                entry is None
                or entry.token_ids != tokens
                or entry.parent_hash != parent_hash
            ):
                break
            matched.append(entry.block_id)
            # LRU bump: move to end (most-recently-used).
            self._entries.move_to_end(h)
            parent_hash = h
        if matched:
            self._hits += 1
        else:
            self._misses += 1
        return matched, len(matched) * self._block_size

    def insert(self, token_ids: Sequence[int], block_ids: Sequence[int]) -> int:
        """Register ``block_ids`` as the KV cache for this ``token_ids`` prefix.

        ``token_ids`` must be block-aligned (``len % block_size == 0``).
        ``block_ids`` must supply one block per ``block_size`` tokens. Blocks
        are refcount-incremented against the manager; duplicates (already-cached
        entries) just LRU-bump, no new reference. Evicts LRU if over capacity.

        Returns the number of *newly-cached* blocks (excludes duplicates).
        """
        if len(token_ids) % self._block_size != 0:
            raise ValueError(
                f"token_ids must be block-aligned (block_size={self._block_size}), "
                f"got length {len(token_ids)}"
            )
        n_blocks = len(token_ids) // self._block_size
        if len(block_ids) != n_blocks:
            raise ValueError(
                f"expected {n_blocks} block_ids for {len(token_ids)} tokens, "
                f"got {len(block_ids)}"
            )

        inserted = 0
        parent_hash = 0
        for i in range(n_blocks):
            tokens = tuple(
                token_ids[i * self._block_size : (i + 1) * self._block_size]
            )
            h = hash((parent_hash, tokens))
            existing = self._entries.get(h)
            if (
                existing is not None
                and existing.token_ids == tokens
                and existing.parent_hash == parent_hash
            ):
                self._entries.move_to_end(h)
                parent_hash = h
                continue

            # New entry. Refcount the block; eviction (if needed) runs AFTER
            # insert so we never evict the block we just inserted.
            self._manager.incref_blocks([block_ids[i]])
            self._entries[h] = _PrefixEntry(
                token_ids=tokens,
                parent_hash=parent_hash,
                block_id=block_ids[i],
            )
            inserted += 1
            parent_hash = h
            self._evict_while_over_capacity()
        return inserted

    def clear(self) -> None:
        """Drop every entry. Decrements all held refcounts."""
        if not self._entries:
            return
        # Batch decref to avoid a free-list.append+loop per call.
        blocks = [e.block_id for e in self._entries.values()]
        self._entries.clear()
        self._manager.decref_blocks(blocks)

    # ─── observability ────────────────────────────────────────────────

    @property
    def cached_blocks(self) -> int:
        return len(self._entries)

    def stats(self) -> PrefixCacheStats:
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total > 0 else 0.0
        return PrefixCacheStats(
            lookups=self._lookups,
            hits=self._hits,
            misses=self._misses,
            hit_rate=hit_rate,
            cached_blocks=len(self._entries),
        )

    # ─── internals ────────────────────────────────────────────────────

    def _evict_while_over_capacity(self) -> None:
        if self._max_entries is None:
            return
        while len(self._entries) > self._max_entries:
            _, evicted = self._entries.popitem(last=False)  # LRU: oldest first
            self._manager.decref_blocks([evicted.block_id])
