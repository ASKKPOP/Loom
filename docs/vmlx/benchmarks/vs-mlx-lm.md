# vMLX vs mlx-lm benchmark

_Generated 2026-04-22T23:15:40+00:00_

Head-to-head on the same model and identical workload.
We boot each server, fire a shared system prompt + varied user suffixes at several concurrency levels, and measure aggregate tokens/sec, TTFT p50/p95, and peak server-process RSS.

## Reproducibility

```bash
python -m vmlx.benchmarks.compare_mlx_lm \
  --model mlx-community/Qwen2.5-0.5B-Instruct-4bit \
  --concurrency 1,4,8,16 \
  --requests-per-level 8 \
  --max-tokens 64
```

**Environment**

- `python`: 3.12.13
- `platform`: macOS-26.4.1-arm64-arm-64bit
- `hardware`: Apple M4 Max (Mac16,9)
- `vmlx`: 0.0.1
- `mlx_lm`: 0.31.3

**Servers**

- `vmlx` — version `0.0.1`, port `49353`
- `mlx-lm` — version `0.31.3`, port `49354`

**Workload**

- model: `mlx-community/Qwen2.5-0.5B-Instruct-4bit`
- concurrency levels: [1, 4, 8, 16]
- requests per level: 8
- max_tokens: 64
- shared system prompt: ~1200 chars (stresses prefix caching)
- user suffix length: ~59 chars

## Results

| server | concurrency | ok/n | agg tok/s | TTFT p50 ms | TTFT p95 ms | peak RSS MB | wall s |
|---|---:|---:|---:|---:|---:|---:|---:|
| mlx-lm | 1 | 8/8 | 233.9 | 70.7 | 112.2 | 528 | 1.77 |
| vmlx | 1 | 8/8 | 393.0 | 30.4 | 59.8 | 528 | 1.05 |
| mlx-lm | 4 | 8/8 | 429.2 | 206.1 | 309.4 | 563 | 0.96 |
| vmlx | 4 | 8/8 | 445.9 | 102.9 | 358.8 | 531 | 0.95 |
| mlx-lm | 8 | 8/8 | 489.2 | 412.1 | 417.8 | 613 | 0.84 |
| vmlx | 8 | 8/8 | 860.8 | 131.2 | 177.1 | 532 | 0.49 |
| mlx-lm | 16 | 8/8 | 490.1 | 410.5 | 416.5 | 613 | 0.84 |
| vmlx | 16 | 8/8 | 869.1 | 172.5 | 172.9 | 533 | 0.49 |

### Ratios (vmlx / mlx-lm)

| concurrency | tok/s ratio (↑ favors vmlx) | TTFT p50 ratio (↓ favors vmlx) | TTFT p95 ratio (↓ favors vmlx) | peak RSS ratio (↓ favors vmlx) |
|---:|---:|---:|---:|---:|
| 1 | 1.68× | 0.43× | 0.53× | 1.00× |
| 4 | 1.04× | 0.50× | 1.16× | 0.94× |
| 8 | 1.76× | 0.32× | 0.42× | 0.87× |
| 16 | 1.77× | 0.42× | 0.42× | 0.87× |

## Honest commentary

- **concurrency 1** — throughput: vMLX wins (1.68×); TTFT p50: vMLX wins (0.43×).
- **concurrency 4** — throughput: parity (1.04×); TTFT p50: vMLX wins (0.50×).
- **concurrency 8** — throughput: vMLX wins (1.76×); TTFT p50: vMLX wins (0.32×).
- **concurrency 16** — throughput: vMLX wins (1.77×); TTFT p50: vMLX wins (0.42×).

Across 3 head-to-head throughput comparisons, vMLX leads in 3 and trails in 0. Numbers reflect a single run on the listed hardware; treat differences under ~10% as noise and rerun to confirm before acting on anything tighter.

## Caveats

- **Single run, no warm-up averaging.** Each data point is from one sweep. Rerun to confirm before drawing conclusions on tight margins.
- **Token count is a proxy.** We count streamed content deltas as a cross-server token estimate — it's consistent but not exact. Absolute tok/s should be compared *between* servers in this report, not against externally measured figures.
- **Effective concurrency is capped at n_per_level (8).** Levels above 8 can't utilize more than that many simultaneous requests in this run, so their numbers should match. Bump `--requests-per-level` to saturate higher concurrency.
- **Model is small (0.5B, 4-bit).** Larger models stress prefill and memory differently; rerun on production-sized weights before planning capacity.
- **Workload is synthetic.** Prompts share a ~1.2k-char system prefix; real traffic may have very different prefix/suffix ratios, which will shift cache hit rates.
