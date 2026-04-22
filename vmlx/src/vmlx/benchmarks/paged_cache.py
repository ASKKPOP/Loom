"""Memory-efficiency benchmark for PagedKVCacheManager.

Runs a simulated mixed-length workload against ``PagedKVCacheManager`` and
reports:

- paged-slot bytes vs. padded-baseline bytes (wasted padding eliminated)
- utilization = committed_tokens / (allocated_blocks * block_size)

The acceptance criterion for vmlx-006 is utilization > 0.80 on a realistic
workload; this script is the reproducible demonstration behind that claim.

Usage:
    python -m vmlx.benchmarks.paged_cache
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from vmlx.cache import PagedCacheConfig, PagedKVCacheManager


@dataclass(frozen=True)
class Scenario:
    name: str
    num_seqs: int
    len_min: int
    len_max: int
    seed: int = 42


SCENARIOS: list[Scenario] = [
    Scenario("tight-mix (40..200)", num_seqs=32, len_min=40, len_max=200),
    Scenario("wide-mix (10..1000)", num_seqs=32, len_min=10, len_max=1000),
    Scenario("long-ctx (500..2000)", num_seqs=16, len_min=500, len_max=2000),
    Scenario("short-chat (20..80)", num_seqs=64, len_min=20, len_max=80),
]

BLOCK_SIZES = [8, 16, 32, 64]


def _alloc_config(block_size: int, max_tokens: int, num_seqs: int) -> PagedCacheConfig:
    # Provision enough blocks to hold every sequence at max length.
    # +1 per sequence covers partial final blocks.
    blocks_needed = num_seqs * ((max_tokens + block_size - 1) // block_size + 1)
    return PagedCacheConfig(
        num_blocks=blocks_needed,
        num_layers=1,
        num_kv_heads=8,
        head_dim=64,
        block_size=block_size,
        dtype="float16",
    )


def _simulate(scenario: Scenario, block_size: int) -> tuple[float, int, int]:
    """Run one scenario. Returns (utilization, paged_slots, padded_slots)."""
    import mlx.core as mx

    rng = random.Random(scenario.seed)
    lengths = [
        rng.randint(scenario.len_min, scenario.len_max) for _ in range(scenario.num_seqs)
    ]
    cfg = _alloc_config(block_size, max(lengths), len(lengths))
    m = PagedKVCacheManager(cfg)
    dtype = getattr(mx, cfg.dtype)

    for i, ln in enumerate(lengths):
        sid = f"s{i}"
        m.open_sequence(sid)
        # Minimal-cost synthetic KV — values don't matter for the allocator.
        k = mx.zeros((ln, cfg.num_kv_heads, cfg.head_dim), dtype=dtype)
        v = mx.zeros((ln, cfg.num_kv_heads, cfg.head_dim), dtype=dtype)
        m.append_kv(sid, layer=0, k=k, v=v)

    util = m.utilization()
    paged_slots = m.num_allocated_blocks * cfg.block_size
    padded_slots = m.padded_baseline_slots()
    return util, paged_slots, padded_slots


def main() -> None:
    print("| scenario | block | utilization | paged slots | padded slots | savings |")
    print("|---|---:|---:|---:|---:|---:|")
    for sc in SCENARIOS:
        for bs in BLOCK_SIZES:
            util, paged, padded = _simulate(sc, bs)
            savings = 1.0 - (paged / padded) if padded > 0 else 0.0
            print(
                f"| {sc.name} | {bs} | {util:.3f} | {paged:>7d} | {padded:>7d} | {savings:+.1%} |"
            )


if __name__ == "__main__":
    main()
