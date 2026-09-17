# Mistral Small 4 119B NVFP4

Known-good single-GB10 vLLM configuration for
[`mistralai/Mistral-Small-4-119B-2603-NVFP4`](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603-NVFP4).

This recipe intentionally does **not** enable EAGLE or another speculative
decoder. On the tested GB10 system, the non-speculative configuration delivered
substantially higher throughput than the official EAGLE draft head.

## Benchmark report

The [full baseline-versus-EAGLE report](benchmarks/2026-09-17-eagle-comparison/)
contains the 72-cell concurrency/reasoning matrix, five summary plots, and
machine-readable CSV/JSON results. Across every tested concurrency and both
reasoning modes, the non-speculative baseline was faster. At concurrency 6 it
delivered 69.25 output tok/s with reasoning disabled, versus 34.95 for EAGLE-1
and 34.50 for EAGLE-3.

## Pinned artifacts

- vLLM: `vllm/vllm-openai:v0.28.0`
- Immutable image: `vllm/vllm-openai@sha256:61fc8a896b0a4fbbbdc063bc4b0dbc25ce98e02b5050c24aeb7830ac02039b14`
- Model revision: `45331841b631f4e281df8e959ea3cc9beb84298a`

## Launch

The model may require accepting its Hugging Face terms and using a token with
access. Export the token without placing it in this repository:

```bash
export HF_TOKEN='hf_...'
export HF_CACHE="$HOME/hf_cache"  # optional; this is the default
./launch.sh
```

Run the script as a user with Docker access. If the host requires `sudo`, retain
the token and recipe settings explicitly:

```bash
sudo --preserve-env=HF_TOKEN,HUGGING_FACE_HUB_TOKEN,HF_CACHE,PORT,CONTAINER_NAME \
  ./launch.sh
```

The OpenAI-compatible API will listen on port `8021`. Override the host port,
cache path, or container name when needed:

```bash
PORT=9000 HF_CACHE=/data/hf_cache CONTAINER_NAME=mistral-small-4 ./launch.sh
```

Test the Responses API:

```bash
curl http://localhost:8021/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "mistral-small-4-119b-nvfp4",
    "input": "Reply with exactly READY.",
    "max_output_tokens": 32,
    "reasoning": {"effort": "none"}
  }'
```

The validated reasoning-effort values are `none` and `high`.

## Validated configuration

- One NVIDIA GB10 GPU with 128 GB unified memory
- `TRITON_MLA` attention backend
- FP8 E4M3 KV cache
- 131,072-token maximum model length
- Chunked prefill and prefix caching enabled
- Up to 8 concurrent sequences
- Mistral tool-call and reasoning parsers
- OpenAI-compatible Responses API

The first cold start must load roughly 66 GiB of checkpoint data and can take
several minutes. Docker reporting the container as running does not mean the API
is ready; wait for `GET /v1/models` to succeed.
