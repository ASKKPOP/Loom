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
# Not yet functional — will serve an MLX model on localhost
vmlx serve <model-id>
```

## License

Apache 2.0 — see [../LICENSE](../LICENSE).
