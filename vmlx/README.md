# vMLX

High-throughput MLX serving engine for Apple Silicon. The inference layer powering [Loom](../README.md), also usable standalone — think *vLLM for MLX*.

## Status

**Alpha (v0.1.0).** Phase 0 complete. Core continuous-batching server is running and benchmarked. See [limitations](#limitations) for what isn't wired yet.

## Install (development)

```bash
# Requires Python 3.12 on macOS arm64
python3.12 -m venv ../.venv
../.venv/bin/pip install -e '.[dev]'
```

## Quickstart

```bash
# Serve a model on localhost:8000 with an OpenAI-compatible API.
# Defaults to the batching engine; pass --engine single for the reference baseline.
vmlx serve mlx-community/Qwen2.5-0.5B-Instruct-4bit

# Override the scheduler width (default: 32):
vmlx serve mlx-community/Qwen2.5-0.5B-Instruct-4bit --max-concurrent 16
```

Then from any OpenAI client — Python SDK, curl, LangChain, LiteLLM, etc.:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
    "messages": [{"role": "user", "content": "Say hi"}],
    "max_tokens": 50
  }'
```

Or with the official `openai` Python SDK:

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed")
resp = client.chat.completions.create(
    model="mlx-community/Qwen2.5-0.5B-Instruct-4bit",
    messages=[{"role": "user", "content": "Say hi"}],
)
print(resp.choices[0].message.content)
```

Streaming works identically — pass `stream=True`.

## Engines

| Engine | When to use |
|---|---|
| `batching` | **Default.** Continuous-batched via `mlx_lm.BatchGenerator`. Many concurrent requests. Higher aggregate throughput. Scheduler width via `--max-concurrent N` (default 32). |
| `single` | Baseline reference. One request at a time. Lowest latency per request. Select with `--engine single`. |

Both satisfy the same protocol — the API server and benchmark harness work with either.

## Features

### Continuous batching

`BatchingEngine` wraps `mlx_lm.BatchGenerator` to process multiple inflight requests in a single GPU pass. Requests are drained as they finish without stalling new arrivals.

### Paged KV cache (data structure)

`PagedKVCacheManager` (`vmlx/src/vmlx/cache/paged.py`) implements block-paged KV storage for Apple unified memory — fixed-size blocks allocated from a pre-reserved pool, ≥0.85 utilization at batch 16, 29–54% savings over padded allocation. The data structure is implemented and tested (29 unit + 3 Metal tests); it is not yet integrated into `BatchingEngine`'s generation path. See [Limitations](#limitations).

### Prefix caching (data structure + TTFT microbenchmark)

`PrefixCache` (`vmlx/src/vmlx/cache/prefix.py`) implements hash-based KV block deduplication for shared system prompts. A microbenchmark against `mlx-community/Qwen2.5-0.5B-Instruct-4bit` with a 1 200-char shared prefix shows **54.5% TTFT reduction** (vs the ≥50% target). Cache stats (hit rate, capacity) are exposed at `GET /admin/stats`. The cache is not yet consulted on the live request path in `vmlx serve`. See [Limitations](#limitations).

### OpenAI-compatible API

`POST /v1/chat/completions` supports streaming (`stream: true`) and non-streaming responses, `GET /v1/models`, `GET /health`, and `GET /admin/stats`. Works with any standard OpenAI client.

### Loom gateway integration

The [Loom](../loom/) product connects to vMLX via the standard `/v1` surface. No vMLX-specific shim is required.

## Benchmark

### Sequential vs concurrent

```bash
# Sequential baseline
python -m vmlx.benchmarks.run \
  --engine single \
  --model mlx-community/Qwen2.5-0.5B-Instruct-4bit \
  --n 20

# Concurrent batching
python -m vmlx.benchmarks.run \
  --engine batching \
  --model mlx-community/Qwen2.5-0.5B-Instruct-4bit \
  --n 8 --concurrent 8
```

Every run appends one line to `vmlx/benchmarks/history.jsonl`.

### Head-to-head vs `mlx_lm.server`

```bash
python -m vmlx.benchmarks.compare_mlx_lm \
  --model mlx-community/Qwen2.5-0.5B-Instruct-4bit \
  --concurrency 1,4,8,16 --requests-per-level 8
```

Boots both `vmlx serve` and `mlx_lm.server` on separate ports, fires a shared-prefix workload at each concurrency level, and writes a markdown report to [`docs/vmlx/benchmarks/vs-mlx-lm.md`](../docs/vmlx/benchmarks/vs-mlx-lm.md).

#### Summary (Apple M4 Max, Qwen2.5-0.5B-4bit, single run)

| concurrency | vmlx tok/s | mlx-lm tok/s | ratio | TTFT p50 ratio |
|---:|---:|---:|---:|---:|
| 1 | 393 | 234 | 1.68× | 0.43× |
| 4 | 446 | 429 | 1.04× (parity) | 0.50× |
| 8 | 861 | 489 | 1.76× | 0.32× |
| 16 | 869 | 490 | 1.77× | 0.42× |

Ratios >1.0× in tok/s favor vMLX; <1.0× in TTFT favor vMLX (lower is faster).
At concurrency 4 the throughput difference is within noise — treat it as a tie.
Full report including caveats: [`docs/vmlx/benchmarks/vs-mlx-lm.md`](../docs/vmlx/benchmarks/vs-mlx-lm.md).

## Limitations

These are deliberately explicit. Anything not listed here is either implemented or not targeted yet.

- **Prefix cache not in serving path.** `PrefixCache` is implemented and tested, but `vmlx serve` does not yet pass it to `create_app`. Inference does not yet benefit from it at runtime.
- **Paged KV cache not in serving path.** `PagedKVCacheManager` is implemented and tested, but `BatchingEngine` does not yet use it for allocation. `mlx_lm.BatchGenerator` manages memory internally.
- **Metal only.** Requires macOS arm64 (Apple Silicon). CPU fallback and non-Metal GPUs are not supported.
- **Single model per server.** One `vmlx serve` process serves one model. Multi-model or hot-swap is not implemented.
- **n=1 only.** The `/v1/chat/completions` endpoint rejects `n > 1`.
- **No tool use / function calling.** The API does not implement OpenAI tool/function calling.

## License

Apache 2.0 — see [../LICENSE](../LICENSE).
