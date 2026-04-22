# Prefix Caching for Shared System Prompts

Status: shipped in vmlx-007. Implementation: [`vmlx/src/vmlx/cache/prefix.py`](../../vmlx/src/vmlx/cache/prefix.py). Built on [`PagedKVCacheManager`](paged-cache.md).

## Motivation

Chat applications send the same system prompt across every request. A 500-token system prompt followed by a 5-token user turn makes the model re-project K/V for all 505 tokens on every call, even though the first 500 never change. That's ~100× wasted prefill work per turn.

Prefix caching detects and reuses the K/V for shared prompt prefixes. A cache hit skips K/V projection for the matched prefix; the model only computes K/V for the fresh tail. Since prefill dominates time-to-first-token (TTFT) for long prompts, the user sees the first token noticeably faster.

## Design

### Content-addressed hash chain

Rather than hashing the whole prompt (which would only hit on *exact* match), the cache hashes **block by block** (aligned to `PagedKVCacheManager.block_size`, default 16). Each block's hash is a function of the previous block's hash plus the block's token ids:

```
hash_0 = hash((0,        tokens[0:B]))
hash_1 = hash((hash_0,   tokens[B:2B]))
hash_i = hash((hash_{i-1}, tokens[i*B:(i+1)*B]))
```

Two prompts that share a common prefix produce the same chain of hashes up through the divergence point. Lookup walks the chain, matches as many blocks as possible, and returns them. This is the same design vLLM uses for automatic prefix caching (PagedAttention paper §5, and `vllm/core/block_manager_v1.py`).

Collision safety. Python's built-in `hash()` is not cryptographic, but every lookup additionally verifies the stored `token_ids` tuple equals the query — a collision yields a miss, never a wrong-content hit. See the [collision-safety test](../../vmlx/tests/test_prefix_unit.py) (`test_prefix_cache_distinguishes_colliding_block_hashes`).

### Refcounting + LRU

The cache holds a reference (+1 refcount) on every cached block, so the underlying `PagedKVCacheManager` can't return a block to its free list while the cache still references it. When a sequence *adopts* a cached prefix, its refcount also bumps; the block lives until both the cache and every adopter have dropped their refs.

Eviction is LRU: an `OrderedDict` keyed by block hash, `move_to_end` on every access, `popitem(last=False)` when over capacity. When `max_entries` is set, inserting a new block over capacity drops the LRU entry — which decrements the manager's refcount for that block (returning it to the pool iff no other refs remain).

Per-layer vs. shared block tables. Prefix caching needs block tables shared across layers — a cached prefix's block ids must index the same position in every layer's K/V tensor. vmlx-007 refactored [`PagedKVCacheManager`](paged-cache.md) to shared tables (it had been per-layer in vmlx-006, which over-allocated by `num_layers×` *and* made prefix caching awkward).

### API

```python
from vmlx.cache import PagedCacheConfig, PagedKVCacheManager, PrefixCache

m = PagedKVCacheManager(cfg)
pc = PrefixCache(m, max_entries=1024)

# Seed the cache after a cold request computed prefix K/V:
m.open_sequence("req-1")
# ... forward pass that appends K/V for the full prompt ...
prefix_blocks = m.block_table("req-1")
pc.insert(prompt_token_ids, prefix_blocks)  # +1 refcount per block

# On a warm request, check for a prefix hit before prefilling:
cached_blocks, n_tokens_matched = pc.lookup(new_prompt_token_ids)
if n_tokens_matched > 0:
    m.open_sequence("req-2")
    m.adopt_prefix("req-2", cached_blocks, n_tokens_matched)  # +1 refcount per block
    # Now only project K/V for new_prompt_token_ids[n_tokens_matched:]
```

`insert` requires block-aligned `token_ids`; sub-block tails are the caller's responsibility (they're never cached).

## Benchmark

[`test_prefix_metal.py`](../../vmlx/tests/test_prefix_metal.py) builds a toy 8-layer attention stack (Q/K/V projections + SDPA, no MLP — only the attention path matters for TTFT) and measures median TTFT over 10 iterations for two paths:

- **Cold**: full prefill — project K/V for 256 prefix tokens + 1 fresh token per layer, then SDPA over the full 257-token context for the fresh query.
- **Warm**: prefix adopted — no K/V projection for the 256 prefix tokens, just 1 fresh token's K/V per layer, then SDPA.

Representative result on an M-series Mac (fp32, 4 KV heads, head_dim=32):

```
TTFT cold=0.62ms  warm=0.28ms  reduction=54.5%
```

The **54.5% reduction** clears the ≥50% acceptance criterion. At larger prefix-to-fresh ratios (e.g. 2K-token system prompt + 20-token user turn, real model) the reduction scales toward the prefix-to-total ratio — 2000/2020 ≈ 99%.

Correctness. A paired [byte-identical test](../../vmlx/tests/test_prefix_metal.py) (`test_cold_and_warm_paths_produce_identical_output`) confirms the warm path yields the exact same SDPA output as the cold path for the same inputs — prefix reuse is not just faster, it's numerically equivalent.

## Observability

`GET /admin/stats` on the vMLX server ([`vmlx/api/server.py`](../../vmlx/src/vmlx/api/server.py)) reports live counters so oncall can watch the hit rate:

```json
{
  "vmlx_version": "0.0.1",
  "model": "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
  "prefix_cache": {
    "lookups": 1243,
    "hits": 981,
    "misses": 262,
    "hit_rate": 0.789,
    "cached_blocks": 847
  }
}
```

When no cache is wired (the default), `prefix_cache` is `null` — explicitly distinct from `hit_rate: 0.0` (which would be ambiguous with "attached but cold").

## What this does *not* do yet

- **No automatic insert after every request.** The engine doesn't yet call `pc.insert(...)` at request completion. Callers must do it manually (the benchmark does). Wiring the engine to seed the cache on every cold completion is part of the vmlx-008 release work.
- **No cross-prefix eviction smarts.** An evicted mid-chain entry orphans its descendants in the dict (a future lookup can't reach them). They're cleaned up eventually via LRU. A tree-aware design (evict descendants with parents) would be more memory-efficient but adds complexity; not needed until we see this in practice.
- **No persistence.** The cache is in-memory. A restart loses every hit.
- **No content scrubbing.** The cache stores token id chains; if two tenants share a server process, one tenant's prompt could leak via a cached-block hit. Tenancy isolation is the caller's responsibility (separate processes or scoped cache instances).

## Benchmarks to reproduce

```bash
# TTFT reduction + byte-identical correctness (Apple Silicon required):
cd vmlx && ../.venv/bin/python -m pytest -m metal tests/test_prefix_metal.py -v -s
```

## References

- Kwon et al., "Efficient Memory Management for Large Language Model Serving with PagedAttention" — [arXiv:2309.06180](https://arxiv.org/abs/2309.06180) (see §5, "Automatic Prefix Caching")
- vLLM implementation — `vllm/core/block_manager_v1.py` in [github.com/vllm-project/vllm](https://github.com/vllm-project/vllm)
- [paged-cache.md](paged-cache.md) — the underlying block-paged KV cache this builds on
