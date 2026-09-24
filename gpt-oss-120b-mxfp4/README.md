# GPT-OSS 120B MXFP4

Candidate single-GB10 vLLM configuration for
[`openai/gpt-oss-120b`](https://huggingface.co/openai/gpt-oss-120b). It is
intended for validation on an NVIDIA DGX Spark with 128 GB unified memory.

The official checkpoint stores its MoE weights in MXFP4, so no separate
quantized checkpoint or online quantization step is needed. The 120B model is
about 63 GB in MXFP4 according to the vLLM launch announcement.

## Pinned artifacts

- vLLM: `vllm/vllm-openai:v0.28.0-ubuntu2404`
- Immutable image: `vllm/vllm-openai@sha256:f8fe15a8039343336945db10494eaad80ef941fe2b2a5fa6649fa38636051a65`
- Model revision: `b5c939de8f754692c1647ca79fbf85e8c1e70f8a`

## Launch

Run the launcher as a user with Docker access. The model is public, so a
Hugging Face token is optional:

```bash
export HF_CACHE="$HOME/hf_cache"  # optional; this is the default
chmod +x launch.sh                 # needed if your copy lost the Git executable bit
./launch.sh
```

If the host requires `sudo`, retain any overrides explicitly:

```bash
sudo --preserve-env=HF_TOKEN,HUGGING_FACE_HUB_TOKEN,HF_CACHE,TIKTOKEN_CACHE,PORT,CONTAINER_NAME,GPU_MEMORY_UTILIZATION,MAX_MODEL_LEN,MAX_NUM_BATCHED_TOKENS,MAX_NUM_SEQS \
  ./launch.sh
```

The OpenAI-compatible API listens on host port `8041`. The settings most
likely to be useful while testing are overridable:

```bash
PORT=9000 MAX_MODEL_LEN=32768 MAX_NUM_SEQS=4 ./launch.sh
```

The first cold start downloads roughly 63 GB of model weights and can take
several minutes. The launcher also downloads the `o200k_base` and `cl100k_base`
tiktoken encoding files from OpenAI's public encoding store, verifies their
SHA-256 hashes, and mounts them read-only for `openai-harmony`. Follow startup
and wait for the API, not just the container:

```bash
docker logs --follow vllm-gpt-oss-120b-mxfp4
curl --fail http://localhost:8041/v1/models
```

Then test the recommended Responses API with low reasoning effort:

```bash
curl --fail http://localhost:8041/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-oss-120b-mxfp4",
    "input": "Reply with exactly READY.",
    "max_output_tokens": 128,
    "reasoning": {"effort": "low"}
  }'
```

GPT-OSS supports `low`, `medium`, and `high` reasoning effort. Function calls
are enabled with vLLM's `openai` tool parser.

## Configuration rationale

- Tensor parallelism is fixed at 1 for the single GB10.
- The official checkpoint's MXFP4 MoE weights provide the requested 4-bit
  storage and execution path.
- FP8 KV cache follows vLLM's Blackwell recipe and preserves context capacity.
- The full 131,072-token model context is exposed by default.
- Eight concurrent sequences is conservative for a workstation with unified
  CPU/GPU memory and can be lowered with `MAX_NUM_SEQS`.
- Prefix caching is disabled to match the upstream GPT-OSS test recipe and
  make synthetic benchmark comparisons consistent.
- The launcher does not set `VLLM_USE_FLASHINFER_MOE_MXFP4_MXFP8`. Upstream
  enables that optimization only for compute capability 10.0; GB10 reports
  12.1, so vLLM 0.28 is allowed to choose its SM121-compatible backend.
- The Harmony vocabulary files are cached outside the container. This prevents
  the first generation request from failing when the container has no outbound
  access to OpenAI's encoding store.

If startup is killed for memory pressure, first retry with a shorter context
and lower memory target:

```bash
GPU_MEMORY_UTILIZATION=0.70 MAX_MODEL_LEN=32768 ./launch.sh
```

This is a candidate recipe until a successful Responses API request is
recorded on the target DGX Spark. Do not label it known-good based only on the
container reaching a running state.

## References

- [vLLM GPT-OSS recipe](https://docs.vllm.ai/projects/recipes/en/stable/OpenAI/GPT-OSS.html)
- [vLLM GPT-OSS launch announcement](https://vllm.ai/blog/2025-08-05-gpt-oss)
