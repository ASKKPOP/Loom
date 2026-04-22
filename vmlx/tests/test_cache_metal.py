"""Metal-tagged correctness tests for PagedKVCacheManager.

These run a small SDPA step through both a paged KV cache and a padded
contiguous baseline, and assert the outputs are byte-identical. This
satisfies the vmlx-006 acceptance criterion that paged reads produce the
same attention output as a contiguous reference.

Metal-tagged because they exercise real ``mx.fast.scaled_dot_product_attention``
on the GPU. Non-Metal cache tests (allocation, round-trip) live in
``test_cache_unit.py``.
"""

from __future__ import annotations

import mlx.core as mx
import pytest

from vmlx.cache import PagedCacheConfig, PagedKVCacheManager


def _fake_qkv(
    t_q: int,
    t_kv: int,
    num_kv_heads: int,
    head_dim: int,
    seed: int = 0,
) -> tuple[mx.array, mx.array, mx.array]:
    """Deterministic Q/K/V tensors.

    Shapes:
        Q: (1, num_kv_heads, t_q, head_dim)  # B=1, using MHA (n_q == n_kv)
        K: (t_kv, num_kv_heads, head_dim)    # to be appended row-by-row
        V: (t_kv, num_kv_heads, head_dim)
    """
    mx.random.seed(seed)
    q = mx.random.normal((1, num_kv_heads, t_q, head_dim), dtype=mx.float32)
    k = mx.random.normal((t_kv, num_kv_heads, head_dim), dtype=mx.float32)
    v = mx.random.normal((t_kv, num_kv_heads, head_dim), dtype=mx.float32)
    return q, k, v


def _sdpa(q: mx.array, k_seq: mx.array, v_seq: mx.array) -> mx.array:
    """Run SDPA given Q shaped (1, H, T_q, D) and K/V shaped (T_kv, H, D).

    Reshape K/V into (1, H, T_kv, D) as SDPA expects.
    """
    h, d = k_seq.shape[1], k_seq.shape[2]
    t_kv = k_seq.shape[0]
    k = k_seq.transpose(1, 0, 2).reshape(1, h, t_kv, d)
    v = v_seq.transpose(1, 0, 2).reshape(1, h, t_kv, d)
    scale = 1.0 / (d**0.5)
    return mx.fast.scaled_dot_product_attention(q, k, v, scale=scale)


@pytest.mark.metal
def test_paged_sdpa_matches_contiguous_baseline_single_step() -> None:
    """Full-prompt prefill path: write all T_kv tokens in one shot and query."""
    num_kv_heads, head_dim, t_q, t_kv = 4, 32, 1, 37
    q, k, v = _fake_qkv(t_q, t_kv, num_kv_heads, head_dim, seed=1)

    # Contiguous baseline.
    reference = _sdpa(q, k, v)

    # Paged path: block_size=8 means ceil(37/8)=5 blocks used.
    cfg = PagedCacheConfig(
        num_blocks=16,
        num_layers=1,
        num_kv_heads=num_kv_heads,
        head_dim=head_dim,
        block_size=8,
        dtype="float32",
    )
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    m.append_kv("s0", layer=0, k=k, v=v)
    pk, pv = m.gather_kv("s0", layer=0)
    paged = _sdpa(q, pk, pv)

    assert mx.array_equal(reference, paged).item() is True


@pytest.mark.metal
def test_paged_sdpa_matches_contiguous_baseline_incremental() -> None:
    """Incremental decode path: prompt prefill then token-by-token extension,
    gathering and running SDPA after each append. Compare against the
    contiguous-K/V baseline gathered at the same logical length."""
    num_kv_heads, head_dim = 4, 32
    total_kv = 40
    prompt_len = 12
    q_per_step = 1  # single-token decode query

    q, k_all, v_all = _fake_qkv(q_per_step, total_kv, num_kv_heads, head_dim, seed=2)

    cfg = PagedCacheConfig(
        num_blocks=16,
        num_layers=1,
        num_kv_heads=num_kv_heads,
        head_dim=head_dim,
        block_size=8,
        dtype="float32",
    )
    m = PagedKVCacheManager(cfg)
    m.open_sequence("s0")
    # Prompt prefill.
    m.append_kv("s0", layer=0, k=k_all[:prompt_len], v=v_all[:prompt_len])

    # Decode: append one token at a time, verify paged SDPA == baseline SDPA.
    for step in range(prompt_len, total_kv):
        m.append_kv(
            "s0",
            layer=0,
            k=k_all[step : step + 1],
            v=v_all[step : step + 1],
        )
        paged_k, paged_v = m.gather_kv("s0", layer=0)
        paged_out = _sdpa(q, paged_k, paged_v)
        ref_out = _sdpa(q, k_all[: step + 1], v_all[: step + 1])
        assert mx.array_equal(ref_out, paged_out).item() is True, (
            f"byte-identical check failed at decode step {step}"
        )


@pytest.mark.metal
def test_paged_sdpa_cross_sequence_isolation() -> None:
    """Two sequences sharing the pool must not contaminate each other's SDPA
    outputs — classic correctness check for block-table separation."""
    num_kv_heads, head_dim = 4, 16
    q_a, k_a, v_a = _fake_qkv(1, 20, num_kv_heads, head_dim, seed=3)
    q_b, k_b, v_b = _fake_qkv(1, 20, num_kv_heads, head_dim, seed=4)

    cfg = PagedCacheConfig(
        num_blocks=16,
        num_layers=1,
        num_kv_heads=num_kv_heads,
        head_dim=head_dim,
        block_size=8,
        dtype="float32",
    )
    m = PagedKVCacheManager(cfg)

    # Interleave opens and appends so the two sequences' blocks are interlaced
    # in pool order — exercises non-contiguous block_table lookups.
    m.open_sequence("a")
    m.open_sequence("b")
    m.append_kv("a", layer=0, k=k_a[:5], v=v_a[:5])
    m.append_kv("b", layer=0, k=k_b[:7], v=v_b[:7])
    m.append_kv("a", layer=0, k=k_a[5:20], v=v_a[5:20])
    m.append_kv("b", layer=0, k=k_b[7:20], v=v_b[7:20])

    pk_a, pv_a = m.gather_kv("a", layer=0)
    pk_b, pv_b = m.gather_kv("b", layer=0)
    paged_a = _sdpa(q_a, pk_a, pv_a)
    paged_b = _sdpa(q_b, pk_b, pv_b)

    ref_a = _sdpa(q_a, k_a, v_a)
    ref_b = _sdpa(q_b, k_b, v_b)

    assert mx.array_equal(ref_a, paged_a).item() is True
    assert mx.array_equal(ref_b, paged_b).item() is True
