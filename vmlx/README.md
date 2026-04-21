# vMLX

High-throughput MLX serving engine for Apple Silicon. The inference layer powering [Loom](../README.md), also usable standalone — think *vLLM for MLX*.

## Status

**Pre-alpha.** Phase 0 work in progress — see [../tasks/tasks.json](../tasks/tasks.json) for the current backlog.

Today vMLX is a skeleton. Targeted capabilities:

- Continuous batching on Metal
- Paged KV cache adapted for Apple unified memory
- Prefix caching
- Speculative decoding
- OpenAI + Anthropic API-compatible surfaces

## Install (development)

```bash
# Requires Python 3.12 on macOS arm64
python3.12 -m venv ../.venv
../.venv/bin/pip install -e '.[dev]'
```

## Quickstart

```bash
# Serve a model on localhost:8000 with an OpenAI-compatible API
vmlx serve mlx-community/Qwen2.5-0.5B-Instruct-4bit
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
| `single` | Baseline reference. One request at a time. Lowest latency per request. |
| `batching` | Continuous-batched. Many concurrent requests. Massively higher aggregate throughput. Backed by `mlx_lm.BatchGenerator`. |

Both satisfy the same protocol — the API server and benchmark harness work with either.

## Benchmark

Sequential baseline:

```bash
python -m vmlx.benchmarks.run \
  --engine single \
  --model mlx-community/Qwen2.5-0.5B-Instruct-4bit \
  --n 20
```

Concurrent batching:

```bash
python -m vmlx.benchmarks.run \
  --engine batching \
  --model mlx-community/Qwen2.5-0.5B-Instruct-4bit \
  --n 8 --concurrent 8
```

Every run appends one line to `vmlx/benchmarks/history.jsonl`.

## License

Apache 2.0 — see [../LICENSE](../LICENSE).
