#!/usr/bin/env bash
set -Eeuo pipefail

# Known-good immutable artifacts. The comment retains the human-readable tag.
# vLLM tag: vllm/vllm-openai:v0.28.0-ubuntu2404
readonly IMAGE='vllm/vllm-openai@sha256:f8fe15a8039343336945db10494eaad80ef941fe2b2a5fa6649fa38636051a65'
readonly MODEL='nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4'
readonly MODEL_REVISION='ff433f5493e25d631c9f12b5d55c674229923d02'
readonly MTPV2_MODEL='nvidia/Nemotron-3-Super-120B-A12B-BF16-MTPv2'
readonly MTPV2_REVISION='c929f8a55d0527fea9f58b4cedc9e0c855cfc421'
readonly SERVED_MODEL_NAME='nemotron-3-super-120b-nvfp4'

CONTAINER_NAME="${CONTAINER_NAME:-vllm-nemotron-3-super-120b-nvfp4-mtpv2}"
PORT="${PORT:-8031}"
HF_CACHE="${HF_CACHE:-$HOME/hf_cache}"

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo 'HF_TOKEN must be set in the environment.' >&2
  exit 1
fi

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "PORT must be an integer from 1 through 65535 (got: $PORT)." >&2
  exit 1
fi

if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  echo "A container named '$CONTAINER_NAME' already exists." >&2
  echo "Remove or rename it explicitly before launching this recipe." >&2
  exit 1
fi

mkdir -p "$HF_CACHE"

# Some Hugging Face tooling reads the legacy variable name. Export both without
# embedding the token in this script or passing its value on the command line.
export HUGGING_FACE_HUB_TOKEN="${HUGGING_FACE_HUB_TOKEN:-$HF_TOKEN}"

readonly SPECULATIVE_CONFIG="$(printf \
  '{\"method\":\"mtp\",\"model\":\"%s\",\"revision\":\"%s\",\"num_speculative_tokens\":3,\"moe_backend\":\"triton\"}' \
  "$MTPV2_MODEL" "$MTPV2_REVISION")"

docker run --detach \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --gpus all \
  --ipc host \
  --publish "${PORT}:8031" \
  --volume "${HF_CACHE}:/root/.cache/huggingface" \
  --env HF_TOKEN \
  --env HUGGING_FACE_HUB_TOKEN \
  "$IMAGE" \
  "$MODEL" \
  --revision "$MODEL_REVISION" \
  --served-model-name "$SERVED_MODEL_NAME" \
  --trust-remote-code \
  --tensor-parallel-size 1 \
  --host 0.0.0.0 \
  --port 8031 \
  --gpu-memory-utilization 0.82 \
  --max-model-len 131072 \
  --max-num-batched-tokens 16384 \
  --max-num-seqs 8 \
  --load-format fastsafetensors \
  --attention-backend flashinfer \
  --kv-cache-dtype fp8 \
  --mamba-cache-mode align \
  --mamba-ssm-cache-dtype float32 \
  --speculative-config "$SPECULATIVE_CONFIG" \
  --enable-prefix-caching \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml \
  --reasoning-parser nemotron_v3 \
  --default-chat-template-kwargs '{"enable_thinking":true}'

echo "Started $CONTAINER_NAME."
echo "Wait for readiness: curl --fail http://localhost:${PORT}/v1/models"
