# Qwen3.8-Flash-Next

Known-good single-GB10 vLLM configuration for
[`nvidia/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4),
using two native MTP draft tokens per step.

## Pinned artifacts

- vLLM commit/tag: `8a728663c1c3eeace834a95f5654fa653cc1998c`
- Immutable image: `vllm/vllm-openai@sha256:f5df5cc3302b5f404848c4eca88d7bf7ed5226e151c056da22816d7734644d67`
- Model revision: `fc694b54fb0174e0913e6adf86691ef85a4ead47`
- Runtime overlays: [patch bundle and provenance](patches/)

This checkpoint contains a roughly 47.68-GiB PLE lookup table in addition to
the model weights. The validated one-Spark deployment keeps that table on local
NVMe and stages only the required rows. The supplied overlays are therefore a
required part of this exact recipe, not optional tuning files.

## Download and launch

Keep the checkpoint on local NVMe; random PLE reads over a network filesystem
will severely reduce performance. With the Hugging Face CLI installed:

```bash
export HF_TOKEN='hf_...'
MODEL_DIR="$HOME/hf_cache/Qwen3.8-Flash-Next-NVFP4-nvidia"
hf download nvidia/Qwen3.8-Flash-Next-NVFP4 \
  --revision fc694b54fb0174e0913e6adf86691ef85a4ead47 \
  --local-dir "$MODEL_DIR"
```

Launch as a user with Docker access:

```bash
MODEL_DIR="$HOME/hf_cache/Qwen3.8-Flash-Next-NVFP4-nvidia" ./launch.sh
```

The OpenAI-compatible API listens on port `8000`. Override `PORT`,
`CONTAINER_NAME`, `MODEL_DIR`, or `CACHE_DIR` as needed. `MTP=2` is the
validated default selected by the published 1–10 sweep; changing MTP causes
the launcher to calculate matching CUDA-graph capture sizes, but creates a
different deployment that should be benchmarked separately.

The first start takes roughly ten minutes. Wait for the real readiness check:

```bash
curl --fail http://localhost:8000/v1/models
```

The chat template defaults to thinking off for compatibility, but clients
should still send explicit reasoning controls for every benchmark request.

## Validated configuration

- One NVIDIA GB10 GPU with 128 GB unified memory
- ModelOpt NVFP4 checkpoint and FP8 E4M3 KV cache
- 262,144-token maximum context
- Six maximum sequences and 4,096 maximum batched tokens
- Two MTP draft tokens and a 65,536-token reduced draft vocabulary
- Staged disk-backed PLE lookup with 64 reader threads
- Decode-only CUDA graphs at widths 3, 6, 9, 12, 15, and 18
- Prefix caching disabled
- Qwen3 reasoning parser and Qwen3 XML tool-call parser
- OpenAI-compatible Responses and Chat Completions APIs

## Benchmarks

- [MTP 1–10 parameter sweep (2026-09-12)](benchmarks/2026-09-12-mtp-sweep/)

The MTP sweep selected two draft tokens per step for this single-GB10 setup.
It did not include an MTP-off deployment, so it is a tuning result rather than
a claim about speculative-decoding uplift.
