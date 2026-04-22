"""Unit tests for PrefixCache and the refcount / adopt_prefix APIs on
PagedKVCacheManager added in vmlx-007."""

from __future__ import annotations

import mlx.core as mx
import pytest

from vmlx.cache import PagedCacheConfig, PagedKVCacheManager, PrefixCache


def _cfg(**overrides: int | str) -> PagedCacheConfig:
    base: dict[str, int | str] = {
        "num_blocks": 16,
        "num_layers": 1,
        "num_kv_heads": 2,
        "head_dim": 4,
        "block_size": 4,
        "dtype": "float32",
    }
    base.update(overrides)
    return PagedCacheConfig(**base)  # type: ignore[arg-type]


def _kv(t: int, cfg: PagedCacheConfig) -> tuple[mx.array, mx.array]:
    dtype = getattr(mx, cfg.dtype)
    k = mx.arange(t * cfg.num_kv_heads * cfg.head_dim, dtype=dtype).reshape(
        t, cfg.num_kv_heads, cfg.head_dim
    )
    v = k + 1000.0
    return k, v


# ─── refcount on PagedKVCacheManager ──────────────────────────────────


def test_refcount_starts_zero_on_free_blocks() -> None:
    m = PagedKVCacheManager(_cfg())
    for b in range(_cfg().num_blocks):
        assert m.refcount(b) == 0


def test_allocated_block_has_refcount_one() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s")
    k, v = _kv(4, cfg)
    m.append_kv("s", layer=0, k=k, v=v)
    (block_id,) = m.block_table("s")
    assert m.refcount(block_id) == 1


def test_incref_decref_roundtrip() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s")
    k, v = _kv(4, cfg)
    m.append_kv("s", layer=0, k=k, v=v)
    block_id = m.block_table("s")[0]
    m.incref_blocks([block_id])
    assert m.refcount(block_id) == 2
    returned = m.decref_blocks([block_id])
    assert returned == 0  # still held by the sequence
    assert m.refcount(block_id) == 1


def test_incref_rejects_free_block() -> None:
    m = PagedKVCacheManager(_cfg())
    with pytest.raises(RuntimeError, match="on the free-list"):
        m.incref_blocks([0])


def test_decref_rejects_zero_refcount() -> None:
    m = PagedKVCacheManager(_cfg())
    with pytest.raises(RuntimeError, match="refcount already 0"):
        m.decref_blocks([0])


def test_incref_rejects_unknown_block() -> None:
    m = PagedKVCacheManager(_cfg(num_blocks=4))
    with pytest.raises(ValueError, match="not in pool"):
        m.incref_blocks([99])


def test_shared_block_survives_one_free() -> None:
    """Block with refcount 2 (sequence + cache) stays allocated until BOTH drop."""
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s")
    k, v = _kv(4, cfg)
    m.append_kv("s", layer=0, k=k, v=v)
    (block_id,) = m.block_table("s")

    # Simulate the cache taking a reference.
    m.incref_blocks([block_id])
    assert m.refcount(block_id) == 2

    # Free the sequence: refcount drops to 1, block does NOT return to pool.
    returned = m.free_sequence("s")
    assert returned == 0
    assert m.refcount(block_id) == 1
    assert m.num_free_blocks == cfg.num_blocks - 1

    # Cache drops its ref: now block returns.
    m.decref_blocks([block_id])
    assert m.refcount(block_id) == 0
    assert m.num_free_blocks == cfg.num_blocks


# ─── adopt_prefix ─────────────────────────────────────────────────────


def test_adopt_prefix_shares_blocks_across_sequences() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    # Seed a prefix as sequence "owner".
    m.open_sequence("owner")
    k, v = _kv(8, cfg)  # 2 blocks
    m.append_kv("owner", layer=0, k=k, v=v)
    prefix_blocks = m.block_table("owner")
    assert len(prefix_blocks) == 2
    assert all(m.refcount(b) == 1 for b in prefix_blocks)

    # A new sequence adopts the same prefix.
    m.open_sequence("reader")
    m.adopt_prefix("reader", block_ids=prefix_blocks, num_tokens=8)
    assert m.sequence_length("reader") == 8
    assert m.block_table("reader") == prefix_blocks
    for b in prefix_blocks:
        assert m.refcount(b) == 2

    # Gathered K/V for the reader must equal what the owner wrote.
    got_k, got_v = m.gather_kv("reader", layer=0)
    assert mx.array_equal(got_k, k).item() is True
    assert mx.array_equal(got_v, v).item() is True


def test_adopt_prefix_then_free_preserves_owner() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("owner")
    k, v = _kv(4, cfg)
    m.append_kv("owner", layer=0, k=k, v=v)
    prefix_blocks = m.block_table("owner")

    m.open_sequence("reader")
    m.adopt_prefix("reader", block_ids=prefix_blocks, num_tokens=4)
    m.free_sequence("reader")  # reader drops its ref

    # Owner still holds the blocks → refcount 1, content intact.
    for b in prefix_blocks:
        assert m.refcount(b) == 1
    got_k, _ = m.gather_kv("owner", layer=0)
    assert mx.array_equal(got_k, k).item() is True


def test_adopt_rejects_sequence_with_existing_tokens() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("owner")
    k, v = _kv(4, cfg)
    m.append_kv("owner", layer=0, k=k, v=v)
    blocks = m.block_table("owner")

    m.open_sequence("other")
    m.append_kv("other", layer=0, k=k, v=v)
    with pytest.raises(RuntimeError, match="already has .* tokens"):
        m.adopt_prefix("other", block_ids=blocks, num_tokens=4)


def test_adopt_rejects_mismatched_block_count() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("owner")
    k, v = _kv(8, cfg)
    m.append_kv("owner", layer=0, k=k, v=v)
    blocks = m.block_table("owner")

    m.open_sequence("reader")
    with pytest.raises(ValueError, match="expected .* blocks"):
        # Says 8 tokens → wants 2 blocks, but we pass only 1.
        m.adopt_prefix("reader", block_ids=blocks[:1], num_tokens=8)


# ─── PrefixCache: lookup / insert basics ──────────────────────────────


def test_prefix_cache_empty_lookup_is_miss() -> None:
    m = PagedKVCacheManager(_cfg())
    pc = PrefixCache(m)
    blocks, n = pc.lookup([1, 2, 3, 4, 5, 6, 7, 8])
    assert blocks == []
    assert n == 0
    s = pc.stats()
    assert s.lookups == 1 and s.hits == 0 and s.misses == 1


def test_prefix_cache_roundtrip_full_match() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    pc = PrefixCache(m)
    # Populate: two blocks worth of tokens.
    m.open_sequence("owner")
    k, v = _kv(8, cfg)
    m.append_kv("owner", layer=0, k=k, v=v)
    owner_blocks = m.block_table("owner")

    token_ids = list(range(8))
    inserted = pc.insert(token_ids, owner_blocks)
    assert inserted == 2
    # Cache holds a ref → refcount 2 per block.
    for b in owner_blocks:
        assert m.refcount(b) == 2

    # Lookup of identical prefix matches all blocks.
    matched, n_tokens = pc.lookup(token_ids)
    assert matched == owner_blocks
    assert n_tokens == 8


def test_prefix_cache_partial_match_at_block_boundary() -> None:
    cfg = _cfg()  # block_size=4
    m = PagedKVCacheManager(cfg)
    pc = PrefixCache(m)

    m.open_sequence("owner")
    k, v = _kv(8, cfg)
    m.append_kv("owner", layer=0, k=k, v=v)
    owner_blocks = m.block_table("owner")

    pc.insert([0, 1, 2, 3, 4, 5, 6, 7], owner_blocks)

    # Query shares only the first block's tokens.
    matched, n = pc.lookup([0, 1, 2, 3, 99, 99, 99, 99])
    assert matched == [owner_blocks[0]]
    assert n == 4


def test_prefix_cache_ignores_sub_block_tail() -> None:
    cfg = _cfg()  # block_size=4
    m = PagedKVCacheManager(cfg)
    pc = PrefixCache(m)
    m.open_sequence("owner")
    k, v = _kv(4, cfg)
    m.append_kv("owner", layer=0, k=k, v=v)
    blocks = m.block_table("owner")
    pc.insert([10, 11, 12, 13], blocks)

    # 6 tokens where first 4 are cacheable; trailing 2 are ignored (sub-block).
    matched, n = pc.lookup([10, 11, 12, 13, 14, 15])
    assert matched == blocks
    assert n == 4


def test_prefix_cache_rejects_non_block_aligned_insert() -> None:
    m = PagedKVCacheManager(_cfg())
    pc = PrefixCache(m)
    with pytest.raises(ValueError, match="block-aligned"):
        pc.insert([1, 2, 3], [0])  # 3 tokens with block_size=4 is not aligned


def test_prefix_cache_rejects_mismatched_block_count() -> None:
    m = PagedKVCacheManager(_cfg())
    pc = PrefixCache(m)
    with pytest.raises(ValueError, match="expected 2 block_ids"):
        pc.insert([1, 2, 3, 4, 5, 6, 7, 8], [0])  # 2 blocks worth, only 1 id given


def test_prefix_cache_duplicate_insert_is_idempotent() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    pc = PrefixCache(m)
    m.open_sequence("owner")
    k, v = _kv(4, cfg)
    m.append_kv("owner", layer=0, k=k, v=v)
    blocks = m.block_table("owner")

    assert pc.insert([1, 2, 3, 4], blocks) == 1
    # Re-inserting same prefix doesn't add refs or entries.
    assert pc.insert([1, 2, 3, 4], blocks) == 0
    assert pc.cached_blocks == 1
    assert m.refcount(blocks[0]) == 2  # sequence + cache, not cache×2


# ─── PrefixCache: LRU eviction ────────────────────────────────────────


def test_prefix_cache_evicts_lru_when_full() -> None:
    """max_entries=2 → inserting a 3rd new prefix evicts the oldest."""
    cfg = _cfg(num_blocks=8)
    m = PagedKVCacheManager(cfg)
    # Seed 3 independent single-block prefixes.
    owner_blocks: list[int] = []
    for i in range(3):
        m.open_sequence(f"o{i}")
        k, v = _kv(4, cfg)
        m.append_kv(f"o{i}", layer=0, k=k, v=v)
        owner_blocks.append(m.block_table(f"o{i}")[0])

    pc = PrefixCache(m, max_entries=2)
    pc.insert([0, 0, 0, 0], [owner_blocks[0]])
    pc.insert([1, 1, 1, 1], [owner_blocks[1]])
    assert pc.cached_blocks == 2
    assert m.refcount(owner_blocks[0]) == 2
    assert m.refcount(owner_blocks[1]) == 2

    # Third insert evicts the LRU (owner_blocks[0]).
    pc.insert([2, 2, 2, 2], [owner_blocks[2]])
    assert pc.cached_blocks == 2
    assert m.refcount(owner_blocks[0]) == 1  # cache dropped its ref
    assert m.refcount(owner_blocks[1]) == 2
    assert m.refcount(owner_blocks[2]) == 2


def test_prefix_cache_lookup_bumps_lru() -> None:
    """A successful lookup moves the entry to MRU, protecting it from eviction."""
    cfg = _cfg(num_blocks=8)
    m = PagedKVCacheManager(cfg)
    owner_blocks = []
    for i in range(3):
        m.open_sequence(f"o{i}")
        k, v = _kv(4, cfg)
        m.append_kv(f"o{i}", layer=0, k=k, v=v)
        owner_blocks.append(m.block_table(f"o{i}")[0])

    pc = PrefixCache(m, max_entries=2)
    pc.insert([0, 0, 0, 0], [owner_blocks[0]])
    pc.insert([1, 1, 1, 1], [owner_blocks[1]])

    # Bump block 0 via lookup; now block 1 is the LRU.
    pc.lookup([0, 0, 0, 0])

    # Inserting a third prefix should evict block 1 (LRU), not block 0.
    pc.insert([2, 2, 2, 2], [owner_blocks[2]])
    assert m.refcount(owner_blocks[0]) == 2  # still cached
    assert m.refcount(owner_blocks[1]) == 1  # evicted
    assert m.refcount(owner_blocks[2]) == 2


def test_prefix_cache_clear_drops_all_refs() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    pc = PrefixCache(m)
    m.open_sequence("owner")
    k, v = _kv(4, cfg)
    m.append_kv("owner", layer=0, k=k, v=v)
    blocks = m.block_table("owner")
    pc.insert([1, 2, 3, 4], blocks)
    assert m.refcount(blocks[0]) == 2

    pc.clear()
    assert pc.cached_blocks == 0
    assert m.refcount(blocks[0]) == 1


# ─── PrefixCache: stats ───────────────────────────────────────────────


def test_prefix_cache_stats_track_hit_rate() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    pc = PrefixCache(m)
    m.open_sequence("owner")
    k, v = _kv(4, cfg)
    m.append_kv("owner", layer=0, k=k, v=v)
    blocks = m.block_table("owner")
    pc.insert([1, 2, 3, 4], blocks)

    pc.lookup([1, 2, 3, 4])  # hit
    pc.lookup([9, 9, 9, 9])  # miss
    pc.lookup([1, 2, 3, 4])  # hit

    s = pc.stats()
    assert s.lookups == 3
    assert s.hits == 2
    assert s.misses == 1
    assert s.hit_rate == pytest.approx(2 / 3)
    assert s.cached_blocks == 1


def test_prefix_cache_stats_zero_when_idle() -> None:
    m = PagedKVCacheManager(_cfg())
    pc = PrefixCache(m)
    s = pc.stats()
    assert s.lookups == 0
    assert s.hits == 0
    assert s.hit_rate == 0.0


def test_prefix_cache_rejects_bad_max_entries() -> None:
    m = PagedKVCacheManager(_cfg())
    with pytest.raises(ValueError, match="must be positive or None"):
        PrefixCache(m, max_entries=0)


# ─── Hash collision safety ────────────────────────────────────────────


def test_prefix_cache_distinguishes_colliding_block_hashes() -> None:
    """Even if hash() of (parent, tokens) collides across different token
    sequences, the stored tokens tuple must be verified before declaring
    a hit. Directly inject a bogus entry at the hash key of a query that
    was NOT cached, and confirm lookup treats it as a miss."""
    from vmlx.cache.prefix import _PrefixEntry

    m = PagedKVCacheManager(_cfg())
    pc = PrefixCache(m)
    m.open_sequence("o")
    k, v = _kv(4, _cfg())
    m.append_kv("o", layer=0, k=k, v=v)
    blocks = m.block_table("o")

    # Simulate a collision: inject a forged entry at the hash key that
    # the query [7, 8, 9, 10] WOULD compute, but tag it with different
    # stored tokens. The lookup must verify tokens and reject.
    target_hash = hash((0, (7, 8, 9, 10)))
    m.incref_blocks(blocks)  # account for the new "cache" ref we're forging
    pc._entries[target_hash] = _PrefixEntry(
        token_ids=(1, 2, 3, 4),  # different from the query!
        parent_hash=0,
        block_id=blocks[0],
    )

    matched, n = pc.lookup([7, 8, 9, 10])
    assert matched == []
    assert n == 0
