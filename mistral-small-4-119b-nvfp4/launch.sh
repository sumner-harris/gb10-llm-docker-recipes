#!/usr/bin/env bash
set -Eeuo pipefail

# Known-good immutable artifacts. The comments retain their human-readable tags.
# vLLM tag: vllm/vllm-openai:v0.28.0
readonly IMAGE='vllm/vllm-openai@sha256:61fc8a896b0a4fbbbdc063bc4b0dbc25ce98e02b5050c24aeb7830ac02039b14'
readonly MODEL='mistralai/Mistral-Small-4-119B-2603-NVFP4'
readonly MODEL_REVISION='45331841b631f4e281df8e959ea3cc9beb84298a'
readonly SERVED_MODEL_NAME='mistral-small-4-119b-nvfp4'

CONTAINER_NAME="${CONTAINER_NAME:-vllm-mistral-small-4-119b-nvfp4}"
PORT="${PORT:-8021}"
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

docker run --detach \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --gpus all \
  --ipc host \
  --publish "${PORT}:8021" \
  --volume "${HF_CACHE}:/root/.cache/huggingface" \
  --env HF_TOKEN \
  --env HUGGING_FACE_HUB_TOKEN \
  "$IMAGE" \
  "$MODEL" \
  --revision "$MODEL_REVISION" \
  --served-model-name "$SERVED_MODEL_NAME" \
  --host 0.0.0.0 \
  --port 8021 \
  --tensor-parallel-size 1 \
  --attention-backend TRITON_MLA \
  --kv-cache-dtype fp8_e4m3 \
  --gpu-memory-utilization 0.85 \
  --max-model-len 131072 \
  --max-num-batched-tokens 4096 \
  --max-num-seqs 8 \
  --enable-chunked-prefill \
  --enable-prefix-caching \
  --tool-call-parser mistral \
  --enable-auto-tool-choice \
  --reasoning-parser mistral

echo "Started $CONTAINER_NAME."
echo "Wait for readiness: curl --fail http://localhost:${PORT}/v1/models"
