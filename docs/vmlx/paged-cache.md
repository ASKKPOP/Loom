# Paged KV Cache for Apple Unified Memory

Status: shipped in vmlx-006. Implementation: [`vmlx/src/vmlx/cache/paged.py`](../../vmlx/src/vmlx/cache/paged.py).

## Motivation

The naïve per-sequence KV cache allocates a contiguous `(max_len, num_kv_heads, head_dim)` tensor per sequence per layer. Two costs follow:

1. **Internal fragmentation.** Every sequence pads to the batch's longest, even if its own context is much shorter. For a mixed chat workload (lengths 20–200, `max_len=200`), the average sequence uses ~55% of its allocation.
2. **Rigid scheduling.** The scheduler can't admit a new sequence unless it reserves `max_len` slots up front, even when most in-flight sequences are using a fraction of theirs.

The PagedAttention design (vLLM, [arXiv:2309.06180](https://arxiv.org/abs/2309.06180)) replaces the per-sequence contiguous tensor with a **pool of fixed-size blocks** and a per-sequence **block table** mapping logical positions to (block_id, block_offset). Sequences grow block-by-block on demand. Internal fragmentation is bounded by `block_size - 1` tokens per sequence.

## Why this is a natural fit for Apple Silicon

On CUDA systems, paged caches are non-trivial because CPU-resident block tables must be kept in sync with GPU-resident KV tensors; host↔device copies per allocation are expensive, and custom kernels are needed to gather from non-contiguous block layouts without those copies.

Apple Silicon's **unified memory architecture** collapses that distinction. The scheduler (CPU) and the attention kernel (GPU) share the same physical memory. An `mx.array` can be indexed on the Python side (scheduler writes `k_cache[block_id, block_pos] = new_kv`) and then read by `mx.fast.scaled_dot_product_attention` on the GPU without any transfer. Allocation is a free-list pop; writes are direct stores; reads are `mx.take`.

The code leans on this property throughout — see `paged.py:216` (`append_kv` mutates the pool directly) and `paged.py:248` (`gather_kv` uses `mx.take` to materialize a logically-contiguous view). No custom Metal kernel is needed for correctness.

## Data layout

One (K, V) pool **per layer**, each shaped:

```
(num_blocks, block_size, num_kv_heads, head_dim)
```

Total pool bytes: `2 × num_layers × num_blocks × block_size × num_kv_heads × head_dim × sizeof(dtype)`.

Per-layer per-sequence state:

```
_LayerSlot(
    blocks: list[int]  # block ids, in logical order
    length: int        # logical tokens written
)
```

The block table is per-layer — not shared across layers — so layers are fully independent. In practice all layers advance in lockstep during one forward pass (same `T` appended to each), but decoupling them simplifies the API and the test surface.

## Block size

The design rationale for the default **`block_size = 16`**:

| factor | analysis |
|---|---|
| **Worst-case waste** | `block_size - 1` tokens per sequence per layer. At B=16 this is 15 tokens; negligible for `avg_len >> 16`. |
| **Alignment** | For `head_dim=64`, `num_kv_heads=8`, fp16 storage, one block is `16 × 8 × 64 × 2 = 16 KiB` — cache-line aligned on Apple Silicon's 128-byte lines, matching the memory-system granularity. |
| **Metadata overhead** | Block tables grow `O(seq_len / block_size)`. At B=16 a 2K-token sequence has a 128-entry table — trivial. |
| **vLLM parity** | vLLM defaults to B=16. Keeping the default the same makes cross-reference easier and avoids surprising anyone coming from CUDA. |

### Empirical validation

`python -m vmlx.benchmarks.paged_cache` runs four simulated workloads across four block sizes. Representative output (fp16, `num_kv_heads=8`, `head_dim=64`):

| scenario | block | utilization | paged slots | padded slots | savings |
|---|---:|---:|---:|---:|---:|
| tight-mix (40..200) | 8  | 0.972 | 3 664  | 6 208  | +41.0% |
| tight-mix (40..200) | **16** | **0.947** | **3 760**  | **6 208**  | **+39.4%** |
| tight-mix (40..200) | 32 | 0.883 | 4 032  | 6 208  | +35.1% |
| tight-mix (40..200) | 64 | 0.807 | 4 416  | 6 208  | +28.9% |
| wide-mix (10..1000) | **16** | **0.981** | 13 600 | 29 536 | +54.0% |
| long-ctx (500..2000) | **16** | **0.991** | 16 816 | 30 160 | +44.2% |
| short-chat (20..80) | **16** | **0.851** | 3 456  | 4 928  | +29.9% |

B=16 hits **>0.85 utilization on every scenario we tested** and preserves **>29% savings vs. padded baselines**. B=8 is marginally better on utilization but doubles block-table overhead. B=32 and B=64 degrade on short-context workloads (B=64 collapses to the padded baseline on short-chat).

## API

```python
from vmlx.cache import PagedCacheConfig, PagedKVCacheManager

cfg = PagedCacheConfig(
    num_blocks=512,
    num_layers=24,
    num_kv_heads=8,
    head_dim=64,
    block_size=16,
    dtype="float16",
)
m = PagedKVCacheManager(cfg)

m.open_sequence("req-42")
# During forward pass, per layer:
m.append_kv("req-42", layer=0, k=k_0, v=v_0)  # shape (T, H, D)
# Later, when running SDPA on this sequence:
k_seq, v_seq = m.gather_kv("req-42", layer=0)  # shape (L, H, D)
# ... run mx.fast.scaled_dot_product_attention(q, k_seq, v_seq, ...)
m.free_sequence("req-42")  # returns blocks to the pool
```

`gather_kv` returns fresh arrays (via `mx.take` + `reshape` + slice to logical length), so subsequent appends can't clobber them.

## Correctness guarantees

The [metal-tagged test suite](../../vmlx/tests/test_cache_metal.py) asserts **byte-identical SDPA output** between the paged cache and a contiguous baseline for three scenarios:

1. **Single-step prefill** — 37-token prompt written in one call, SDPA over the full sequence.
2. **Incremental decode** — 12-token prefill then 28 single-token appends, SDPA after each.
3. **Cross-sequence isolation** — two interleaved sequences sharing the pool, each gathered and verified.

The unit suite ([`test_cache_unit.py`](../../vmlx/tests/test_cache_unit.py), 26 tests) covers allocator state, block-boundary appends, multi-layer independence, and pool-exhaustion errors.

## Concurrency contract

`PagedKVCacheManager` is **not thread-safe**. The expected caller is a single scheduler thread that owns all KV state — this matches the existing [`BatchingEngine`](../../vmlx/src/vmlx/engine/batching.py) design, where one scheduler thread is the sole caller of `insert()`/`next_generated()`/`remove()`. External callers needing cross-thread access must wrap with a lock.

## What this does *not* do yet

- **No integration with `BatchingEngine`.** The production batching path (`BatchingEngine` in `vmlx/engine/batching.py`) still delegates KV management to `mlx_lm.BatchGenerator`. `PagedKVCacheManager` is the building block that a future custom scheduler will own; wiring it into the forward pass requires a custom transformer forward (per-layer append + gather + SDPA) and is scoped to a follow-up task.
- **No prefix sharing / copy-on-write.** Blocks are allocated exclusively per sequence. Prefix caching (shared blocks across sequences with the same prompt prefix) is a natural extension but out of scope here.
- **No eviction.** When the pool is exhausted `append_kv` raises `MemoryError`. A scheduler-level admission-control policy (reject, preempt, or swap) lives above this layer.

## Benchmarks to reproduce

```bash
# Utilization simulation (non-Metal, pure allocator):
.venv/bin/python -m vmlx.benchmarks.paged_cache

# Correctness (requires Apple Silicon + Metal):
cd vmlx && ../.venv/bin/python -m pytest -m metal tests/test_cache_metal.py -v
```

## References

- Kwon et al., "Efficient Memory Management for Large Language Model Serving with PagedAttention" — [arXiv:2309.06180](https://arxiv.org/abs/2309.06180)
- vLLM PagedAttention kernel — [github.com/vllm-project/vllm](https://github.com/vllm-project/vllm)
- MLX unified-memory model — [ml-explore.github.io/mlx](https://ml-explore.github.io/mlx/build/html/usage/unified_memory.html)
