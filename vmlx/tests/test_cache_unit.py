"""Unit tests for PagedKVCacheManager.

These use small mx arrays but no model, no Metal GPU specifics — they
exercise allocation, append/gather round-trip, fragmentation, utilization,
and error paths.
"""

from __future__ import annotations

import mlx.core as mx
import pytest

from vmlx.cache import PagedCacheConfig, PagedKVCacheManager


def _cfg(**overrides: int | str) -> PagedCacheConfig:
    base: dict[str, int | str] = {
        "num_blocks": 8,
        "num_layers": 2,
        "num_kv_heads": 2,
        "head_dim": 4,
        "block_size": 4,
        "dtype": "float32",
    }
    base.update(overrides)
    return PagedCacheConfig(**base)  # type: ignore[arg-type]


def _kv(t: int, cfg: PagedCacheConfig) -> tuple[mx.array, mx.array]:
    """Deterministic KV tensors shaped (t, num_kv_heads, head_dim).

    Values encode position so tests can verify which token landed where.
    """
    dtype = getattr(mx, cfg.dtype)
    k = mx.arange(t * cfg.num_kv_heads * cfg.head_dim, dtype=dtype).reshape(
        t, cfg.num_kv_heads, cfg.head_dim
    )
    v = k + 1000.0
    return k, v


# ─── config validation ─────────────────────────────────────────────────


@pytest.mark.parametrize("field", ["num_blocks", "block_size", "num_layers", "num_kv_heads", "head_dim"])
def test_config_rejects_non_positive(field: str) -> None:
    kwargs = {"num_blocks": 4, "num_layers": 1, "num_kv_heads": 1, "head_dim": 4}
    kwargs[field] = 0
    with pytest.raises(ValueError, match=f"{field} must be positive"):
        PagedCacheConfig(**kwargs)  # type: ignore[arg-type]


def test_config_rejects_unknown_dtype() -> None:
    with pytest.raises(ValueError, match="unknown mx dtype"):
        PagedKVCacheManager(
            PagedCacheConfig(
                num_blocks=1,
                num_layers=1,
                num_kv_heads=1,
                head_dim=4,
                dtype="bogus_dtype",
            )
        )


# ─── allocator ────────────────────────────────────────────────────────


def test_initial_state() -> None:
    m = PagedKVCacheManager(_cfg())
    assert m.num_blocks == 8
    assert m.block_size == 4
    assert m.num_free_blocks == 8
    assert m.num_allocated_blocks == 0
    assert m.utilization() == 1.0  # nothing allocated, no waste
    assert m.active_sequence_ids() == []


def test_open_close_sequence() -> None:
    m = PagedKVCacheManager(_cfg())
    assert not m.has_sequence("s0")
    m.open_sequence("s0")
    assert m.has_sequence("s0")
    assert m.sequence_length("s0") == 0
    assert m.block_table("s0") == []
    m.free_sequence("s0")
    assert not m.has_sequence("s0")


def test_open_same_sequence_twice_raises() -> None:
    m = PagedKVCacheManager(_cfg())
    m.open_sequence("s0")
    with pytest.raises(ValueError, match="already open"):
        m.open_sequence("s0")


def test_free_unknown_sequence_is_noop() -> None:
    m = PagedKVCacheManager(_cfg())
    assert m.free_sequence("ghost") == 0


def test_free_returns_block_count() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    k, v = _kv(9, cfg)  # spans 3 blocks (ceil(9/4))
    m.append_kv("s0", layer=0, k=k, v=v)
    assert m.num_allocated_blocks == 3
    assert m.free_sequence("s0") == 3
    assert m.num_free_blocks == cfg.num_blocks


# ─── append / gather round-trip ───────────────────────────────────────


def test_append_within_single_block() -> None:
    cfg = _cfg()  # block_size=4
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    k, v = _kv(3, cfg)
    m.append_kv("s0", layer=0, k=k, v=v)
    assert m.sequence_length("s0") == 3
    assert m.num_allocated_blocks == 1

    got_k, got_v = m.gather_kv("s0", layer=0)
    assert got_k.shape == (3, cfg.num_kv_heads, cfg.head_dim)
    assert mx.array_equal(got_k, k).item() is True
    assert mx.array_equal(got_v, v).item() is True


def test_append_crosses_block_boundary() -> None:
    cfg = _cfg()  # block_size=4
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    k, v = _kv(7, cfg)
    m.append_kv("s0", layer=0, k=k, v=v)
    assert m.sequence_length("s0") == 7
    assert m.num_allocated_blocks == 2

    got_k, got_v = m.gather_kv("s0", layer=0)
    assert mx.array_equal(got_k, k).item() is True
    assert mx.array_equal(got_v, v).item() is True


def test_append_in_chunks_equals_append_at_once() -> None:
    """Incremental appends (prompt prefill then token-by-token decode)
    must yield the same contents as a single bulk append."""
    cfg = _cfg()
    m_bulk = PagedKVCacheManager(cfg)
    m_bulk.open_sequence("s0")
    k_all, v_all = _kv(10, cfg)
    m_bulk.append_kv("s0", layer=0, k=k_all, v=v_all)
    bulk_k, bulk_v = m_bulk.gather_kv("s0", layer=0)

    m_chunk = PagedKVCacheManager(cfg)
    m_chunk.open_sequence("s0")
    # Prompt: 6 tokens, then 4 one-token decode steps.
    m_chunk.append_kv("s0", layer=0, k=k_all[:6], v=v_all[:6])
    for i in range(6, 10):
        m_chunk.append_kv("s0", layer=0, k=k_all[i : i + 1], v=v_all[i : i + 1])
    chunk_k, chunk_v = m_chunk.gather_kv("s0", layer=0)

    assert mx.array_equal(bulk_k, chunk_k).item() is True
    assert mx.array_equal(bulk_v, chunk_v).item() is True


def test_multiple_sequences_isolated() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("a")
    m.open_sequence("b")
    ka, va = _kv(5, cfg)
    kb, vb = _kv(3, cfg)
    # Make b distinct.
    vb = vb + 10000.0

    m.append_kv("a", layer=0, k=ka, v=va)
    m.append_kv("b", layer=0, k=kb, v=vb)
    # Interleave more appends to a.
    ka2, va2 = _kv(2, cfg)
    ka2 = ka2 + 777.0
    m.append_kv("a", layer=0, k=ka2, v=va2)

    got_ka, got_va = m.gather_kv("a", layer=0)
    got_kb, got_vb = m.gather_kv("b", layer=0)
    assert got_ka.shape == (7, cfg.num_kv_heads, cfg.head_dim)
    assert got_kb.shape == (3, cfg.num_kv_heads, cfg.head_dim)
    assert mx.array_equal(got_ka, mx.concatenate([ka, ka2], axis=0)).item() is True
    assert mx.array_equal(got_kb, kb).item() is True
    assert mx.array_equal(got_vb, vb).item() is True


def test_layers_are_independent() -> None:
    cfg = _cfg(num_layers=2)
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    k0, v0 = _kv(5, cfg)
    k1, v1 = _kv(5, cfg)
    k1 = k1 + 100.0
    v1 = v1 + 200.0
    m.append_kv("s0", layer=0, k=k0, v=v0)
    m.append_kv("s0", layer=1, k=k1, v=v1)

    g0k, g0v = m.gather_kv("s0", layer=0)
    g1k, g1v = m.gather_kv("s0", layer=1)
    assert mx.array_equal(g0k, k0).item() is True
    assert mx.array_equal(g1k, k1).item() is True
    assert mx.array_equal(g0v, v0).item() is True
    assert mx.array_equal(g1v, v1).item() is True


# ─── error paths ──────────────────────────────────────────────────────


def test_append_unknown_sequence_raises() -> None:
    m = PagedKVCacheManager(_cfg())
    k, v = _kv(1, _cfg())
    with pytest.raises(KeyError, match="not open"):
        m.append_kv("ghost", layer=0, k=k, v=v)


def test_append_mismatched_shapes_raises() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    k, _ = _kv(4, cfg)
    bad_v = mx.zeros((3, cfg.num_kv_heads, cfg.head_dim), dtype=getattr(mx, cfg.dtype))
    with pytest.raises(ValueError, match="share axis 0"):
        m.append_kv("s0", layer=0, k=k, v=bad_v)


def test_append_wrong_tail_shape_raises() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    bad_k = mx.zeros((2, cfg.num_kv_heads + 1, cfg.head_dim), dtype=getattr(mx, cfg.dtype))
    bad_v = mx.zeros((2, cfg.num_kv_heads + 1, cfg.head_dim), dtype=getattr(mx, cfg.dtype))
    with pytest.raises(ValueError, match="tail shape"):
        m.append_kv("s0", layer=0, k=bad_k, v=bad_v)


def test_append_bad_layer_raises() -> None:
    cfg = _cfg(num_layers=2)
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    k, v = _kv(1, cfg)
    with pytest.raises(IndexError, match="layer 5 out of range"):
        m.append_kv("s0", layer=5, k=k, v=v)
    with pytest.raises(IndexError, match="layer -1 out of range"):
        m.append_kv("s0", layer=-1, k=k, v=v)


def test_pool_exhaustion_raises_memory_error() -> None:
    cfg = _cfg(num_blocks=2, block_size=4)
    m = PagedKVCacheManager(cfg)
    m.open_sequence("big")
    k, v = _kv(9, cfg)  # 9 tokens → ceil(9/4) = 3 blocks, pool only has 2
    with pytest.raises(MemoryError, match="paged cache exhausted"):
        m.append_kv("big", layer=0, k=k, v=v)


def test_empty_append_is_noop() -> None:
    cfg = _cfg()
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    dtype = getattr(mx, cfg.dtype)
    empty = mx.zeros((0, cfg.num_kv_heads, cfg.head_dim), dtype=dtype)
    m.append_kv("s0", layer=0, k=empty, v=empty)
    assert m.sequence_length("s0") == 0
    assert m.num_allocated_blocks == 0
    k, v = m.gather_kv("s0", layer=0)
    assert k.shape == (0, cfg.num_kv_heads, cfg.head_dim)


# ─── utilization / memory-efficiency ──────────────────────────────────


def test_utilization_fully_packed_block_is_100pct() -> None:
    cfg = _cfg()  # block_size=4
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    k, v = _kv(8, cfg)  # exactly 2 full blocks
    m.append_kv("s0", layer=0, k=k, v=v)
    assert m.utilization() == pytest.approx(1.0)


def test_utilization_partial_block_is_suboptimal() -> None:
    cfg = _cfg()  # block_size=4
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    k, v = _kv(5, cfg)  # 1 full + 1 partial (1/4) → 5/8
    m.append_kv("s0", layer=0, k=k, v=v)
    assert m.utilization() == pytest.approx(5 / 8)


def test_utilization_exceeds_80pct_on_mixed_workload() -> None:
    """Mixed-length workload: the acceptance criterion (>80% KV bytes in
    use vs allocated) holds with ``block_size=16`` on realistic lengths."""
    cfg = _cfg(num_blocks=128, block_size=16)
    m = PagedKVCacheManager(cfg)
    # Realistic-ish prompt/response mix: lengths in [40, 200].
    lengths = [40, 55, 73, 92, 108, 137, 166, 199, 45, 61, 82, 97, 128, 174]
    for i, ln in enumerate(lengths):
        sid = f"s{i}"
        m.open_sequence(sid)
        k, v = _kv(ln, cfg)
        m.append_kv(sid, layer=0, k=k, v=v)

    util = m.utilization()
    assert util > 0.80, f"paged utilization {util:.3f} failed >0.80 criterion"

    # And: the paged allocation is meaningfully smaller than a padded baseline.
    # Baseline pads every sequence to max_len across every layer.
    total_committed = sum(lengths)
    padded_slots = max(lengths) * len(lengths) * cfg.num_layers
    paged_slots = m.num_allocated_blocks * cfg.block_size
    paged_vs_padded = paged_slots / padded_slots
    assert paged_vs_padded < 0.85, (
        f"paged allocation {paged_slots} vs padded {padded_slots} "
        f"(ratio {paged_vs_padded:.3f}) failed to beat padded baseline"
    )
    # Sanity: padded-baseline helper agrees with our manual calc.
    assert m.padded_baseline_slots() == padded_slots
    assert total_committed == sum(m.sequence_length(f"s{i}") for i in range(len(lengths)))


# ─── fragmentation / free-list behavior ───────────────────────────────


def test_freed_blocks_are_reused_lifo() -> None:
    cfg = _cfg(num_blocks=4, block_size=4)
    m = PagedKVCacheManager(cfg)
    m.open_sequence("a")
    k, v = _kv(8, cfg)  # 2 blocks
    m.append_kv("a", layer=0, k=k, v=v)
    a_blocks = m.block_table("a")

    m.free_sequence("a")
    assert m.num_free_blocks == 4

    # New sequence should reuse the freed blocks (not allocate beyond the pool).
    m.open_sequence("b")
    kb, vb = _kv(4, cfg)
    m.append_kv("b", layer=0, k=kb, v=vb)
    b_blocks = m.block_table("b")
    assert len(b_blocks) == 1
    # LIFO: the most-recently-freed block is reused first.
    assert b_blocks[0] == a_blocks[-1]
