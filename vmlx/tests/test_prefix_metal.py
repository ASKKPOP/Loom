"""Metal-tagged TTFT reduction benchmark for PrefixCache.

Builds a toy multi-layer transformer forward (Q/K/V projections + SDPA,
no MLP — only the attention path matters for prefill TTFT) and times:

- **Cold**: compute K/V for N prefix tokens + 1 fresh token, then SDPA
            for the fresh token's query.
- **Warm**: adopt prefix's already-populated blocks from the cache
            (no K/V compute for those tokens), then compute K/V for 1
            fresh token + SDPA.

The acceptance criterion for vmlx-007 is ≥50% TTFT reduction on a prefix
hit. At N=256 prefix tokens vs 1 fresh token the K/V-projection work
ratio is ~256:1 per layer, so the expected reduction is well above 50%.

Correctness: we also assert that cold and warm paths produce identical
SDPA output for the fresh token's query (same inputs, same weights).
"""

from __future__ import annotations

import time
from statistics import median

import mlx.core as mx
import pytest

from vmlx.cache import PagedCacheConfig, PagedKVCacheManager, PrefixCache

NUM_LAYERS = 8
NUM_KV_HEADS = 4
HEAD_DIM = 32
D_MODEL = NUM_KV_HEADS * HEAD_DIM
BLOCK_SIZE = 16
PREFIX_LEN = 256  # tokens in the shared system prompt (block-aligned: 16 blocks)
WARMUP_ITERS = 3
MEASURE_ITERS = 10


def _build_weights(seed: int = 1) -> tuple[mx.array, list[mx.array], list[mx.array]]:
    mx.random.seed(seed)
    w_q = mx.random.normal((D_MODEL, D_MODEL), dtype=mx.float32)
    w_k = [mx.random.normal((D_MODEL, D_MODEL), dtype=mx.float32) for _ in range(NUM_LAYERS)]
    w_v = [mx.random.normal((D_MODEL, D_MODEL), dtype=mx.float32) for _ in range(NUM_LAYERS)]
    return w_q, w_k, w_v


def _project(x: mx.array, w: mx.array) -> mx.array:
    """Project (T, D_MODEL) → (T, NUM_KV_HEADS, HEAD_DIM)."""
    y = x @ w  # (T, D_MODEL)
    return y.reshape(y.shape[0], NUM_KV_HEADS, HEAD_DIM)


def _sdpa(q_seq: mx.array, k_seq: mx.array, v_seq: mx.array) -> mx.array:
    """Run SDPA. q_seq=(T_q, H, D), k_seq/v_seq=(T_kv, H, D)."""
    h, d = k_seq.shape[1], k_seq.shape[2]
    t_q = q_seq.shape[0]
    t_kv = k_seq.shape[0]
    q = q_seq.transpose(1, 0, 2).reshape(1, h, t_q, d)
    k = k_seq.transpose(1, 0, 2).reshape(1, h, t_kv, d)
    v = v_seq.transpose(1, 0, 2).reshape(1, h, t_kv, d)
    return mx.fast.scaled_dot_product_attention(q, k, v, scale=1.0 / (d**0.5))


def _make_manager(num_blocks: int = 64) -> PagedKVCacheManager:
    return PagedKVCacheManager(
        PagedCacheConfig(
            num_blocks=num_blocks,
            num_layers=NUM_LAYERS,
            num_kv_heads=NUM_KV_HEADS,
            head_dim=HEAD_DIM,
            block_size=BLOCK_SIZE,
            dtype="float32",
        )
    )


def _seed_prefix(
    m: PagedKVCacheManager,
    pc: PrefixCache,
    prefix_embeddings: mx.array,  # (PREFIX_LEN, D_MODEL)
    prefix_tokens: list[int],
    w_k: list[mx.array],
    w_v: list[mx.array],
) -> list[int]:
    """Compute prefix K/V and register the blocks in the PrefixCache.

    This simulates the one-time "first request with this system prompt"
    cost: it's paid once and amortized across every warm request after.
    """
    seed_seq = "prefix-seed"
    m.open_sequence(seed_seq)
    for layer in range(NUM_LAYERS):
        k = _project(prefix_embeddings, w_k[layer])
        v = _project(prefix_embeddings, w_v[layer])
        m.append_kv(seed_seq, layer, k, v)
    # All layers have identical block tables in lockstep usage → use layer 0.
    prefix_blocks = m.block_table(seed_seq)
    pc.insert(prefix_tokens, prefix_blocks)
    # Drop the seed sequence: the prefix cache's refcounts keep the blocks alive.
    m.free_sequence(seed_seq)
    return prefix_blocks


def _cold_ttft(
    m: PagedKVCacheManager,
    prefix_embeddings: mx.array,
    fresh_embedding: mx.array,  # (1, D_MODEL)
    w_q: mx.array,
    w_k: list[mx.array],
    w_v: list[mx.array],
    seq_id: str,
) -> tuple[float, mx.array]:
    """Compute TTFT for a cold request: reproject every prefix token's K/V."""
    mx.eval(prefix_embeddings, fresh_embedding)  # ensure inputs materialized
    start = time.perf_counter()

    m.open_sequence(seq_id)
    # Full prefill: project & append K/V for every prefix token.
    for layer in range(NUM_LAYERS):
        k = _project(prefix_embeddings, w_k[layer])
        v = _project(prefix_embeddings, w_v[layer])
        m.append_kv(seq_id, layer, k, v)
    # Fresh token K/V.
    for layer in range(NUM_LAYERS):
        k = _project(fresh_embedding, w_k[layer])
        v = _project(fresh_embedding, w_v[layer])
        m.append_kv(seq_id, layer, k, v)

    # Fresh token's query.
    q = _project(fresh_embedding, w_q)  # (1, H, D)
    out = None
    for layer in range(NUM_LAYERS):
        k_seq, v_seq = m.gather_kv(seq_id, layer)
        out = _sdpa(q, k_seq, v_seq)
    assert out is not None
    mx.eval(out)  # force completion before measuring
    elapsed = time.perf_counter() - start
    return elapsed, out


def _warm_ttft(
    m: PagedKVCacheManager,
    prefix_blocks: list[int],
    fresh_embedding: mx.array,
    w_q: mx.array,
    w_k: list[mx.array],
    w_v: list[mx.array],
    seq_id: str,
) -> tuple[float, mx.array]:
    """Compute TTFT for a warm request: adopt prefix K/V, only project fresh token."""
    mx.eval(fresh_embedding)
    start = time.perf_counter()

    m.open_sequence(seq_id)
    # Adopt prefix — one call (block table is shared across layers).
    m.adopt_prefix(seq_id, prefix_blocks, PREFIX_LEN)
    # Fresh token K/V.
    for layer in range(NUM_LAYERS):
        k = _project(fresh_embedding, w_k[layer])
        v = _project(fresh_embedding, w_v[layer])
        m.append_kv(seq_id, layer, k, v)

    q = _project(fresh_embedding, w_q)
    out = None
    for layer in range(NUM_LAYERS):
        k_seq, v_seq = m.gather_kv(seq_id, layer)
        out = _sdpa(q, k_seq, v_seq)
    assert out is not None
    mx.eval(out)
    elapsed = time.perf_counter() - start
    return elapsed, out


@pytest.mark.metal
def test_prefix_hit_reduces_ttft_by_50pct() -> None:
    """Acceptance criterion: ≥50% TTFT reduction on prefix hit.

    Measures median TTFT over MEASURE_ITERS iterations of each path,
    after WARMUP_ITERS to stabilize cache state and MLX JIT.
    """
    w_q, w_k, w_v = _build_weights()
    mx.random.seed(2)
    prefix_emb = mx.random.normal((PREFIX_LEN, D_MODEL), dtype=mx.float32)
    fresh_emb = mx.random.normal((1, D_MODEL), dtype=mx.float32)
    # Ensure the prefix length is block-aligned for the PrefixCache.
    assert PREFIX_LEN % BLOCK_SIZE == 0
    prefix_tokens = list(range(PREFIX_LEN))

    # One persistent manager + cache across both paths so prefix blocks
    # survive between runs.
    m = _make_manager()
    pc = PrefixCache(m)
    prefix_blocks = _seed_prefix(m, pc, prefix_emb, prefix_tokens, w_k, w_v)

    # Warmup.
    for i in range(WARMUP_ITERS):
        t, _ = _cold_ttft(m, prefix_emb, fresh_emb, w_q, w_k, w_v, f"cold-w{i}")
        m.free_sequence(f"cold-w{i}")
        t, _ = _warm_ttft(m, prefix_blocks, fresh_emb, w_q, w_k, w_v, f"warm-w{i}")
        m.free_sequence(f"warm-w{i}")

    cold_times: list[float] = []
    warm_times: list[float] = []
    for i in range(MEASURE_ITERS):
        t, _ = _cold_ttft(m, prefix_emb, fresh_emb, w_q, w_k, w_v, f"cold-{i}")
        m.free_sequence(f"cold-{i}")
        cold_times.append(t)
        t, _ = _warm_ttft(m, prefix_blocks, fresh_emb, w_q, w_k, w_v, f"warm-{i}")
        m.free_sequence(f"warm-{i}")
        warm_times.append(t)

    cold_median = median(cold_times)
    warm_median = median(warm_times)
    reduction = (cold_median - warm_median) / cold_median

    print(
        f"\nTTFT cold={cold_median * 1000:.2f}ms  "
        f"warm={warm_median * 1000:.2f}ms  "
        f"reduction={reduction:.1%}"
    )
    assert reduction >= 0.50, (
        f"prefix hit TTFT reduction {reduction:.1%} failed to meet "
        f"≥50% acceptance criterion (cold={cold_median * 1000:.2f}ms, "
        f"warm={warm_median * 1000:.2f}ms)"
    )


@pytest.mark.metal
def test_cold_and_warm_paths_produce_identical_output() -> None:
    """Correctness: the warm path (prefix adopted) must yield the same
    SDPA output as the cold path (prefix recomputed), byte-identical."""
    w_q, w_k, w_v = _build_weights()
    mx.random.seed(3)
    prefix_emb = mx.random.normal((PREFIX_LEN, D_MODEL), dtype=mx.float32)
    fresh_emb = mx.random.normal((1, D_MODEL), dtype=mx.float32)

    m = _make_manager()
    pc = PrefixCache(m)
    prefix_blocks = _seed_prefix(
        m, pc, prefix_emb, list(range(PREFIX_LEN)), w_k, w_v
    )

    _, cold_out = _cold_ttft(m, prefix_emb, fresh_emb, w_q, w_k, w_v, "cold")
    m.free_sequence("cold")
    _, warm_out = _warm_ttft(m, prefix_blocks, fresh_emb, w_q, w_k, w_v, "warm")
    m.free_sequence("warm")

    assert mx.array_equal(cold_out, warm_out).item() is True


@pytest.mark.metal
def test_prefix_cache_stats_reflect_hit_on_lookup() -> None:
    """Reading back the PrefixCache stats confirms a successful lookup
    increments hit count (wired to /admin/stats reporting)."""
    w_q, w_k, w_v = _build_weights()
    mx.random.seed(4)
    prefix_emb = mx.random.normal((PREFIX_LEN, D_MODEL), dtype=mx.float32)
    tokens = list(range(PREFIX_LEN))

    m = _make_manager()
    pc = PrefixCache(m)
    _seed_prefix(m, pc, prefix_emb, tokens, w_k, w_v)

    s_before = pc.stats()
    blocks, n_matched = pc.lookup(tokens)
    s_after = pc.stats()

    assert len(blocks) == PREFIX_LEN // BLOCK_SIZE
    assert n_matched == PREFIX_LEN
    assert s_after.hits == s_before.hits + 1
    assert s_after.lookups == s_before.lookups + 1
    assert s_after.hit_rate > 0.0
