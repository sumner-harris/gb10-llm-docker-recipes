#!/usr/bin/env bash
set -Eeuo pipefail

# Known-good artifacts elsewhere in this repository use this ARM64-capable
# Ubuntu 24.04 image. The comment retains its human-readable tag.
# vLLM tag: vllm/vllm-openai:v0.28.0-ubuntu2404
readonly IMAGE='vllm/vllm-openai@sha256:f8fe15a8039343336945db10494eaad80ef941fe2b2a5fa6649fa38636051a65'
readonly MODEL='openai/gpt-oss-120b'
readonly MODEL_REVISION='b5c939de8f754692c1647ca79fbf85e8c1e70f8a'
readonly SERVED_MODEL_NAME='gpt-oss-120b-mxfp4'

CONTAINER_NAME="${CONTAINER_NAME:-vllm-gpt-oss-120b-mxfp4}"
PORT="${PORT:-8041}"
HF_CACHE="${HF_CACHE:-$HOME/hf_cache}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.80}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-131072}"
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-8192}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-8}"

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "PORT must be an integer from 1 through 65535 (got: $PORT)." >&2
  exit 1
fi

for value_name in MAX_MODEL_LEN MAX_NUM_BATCHED_TOKENS MAX_NUM_SEQS; do
  value="${!value_name}"
  if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "$value_name must be a positive integer (got: $value)." >&2
    exit 1
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo 'docker was not found in PATH.' >&2
  exit 1
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo 'nvidia-smi was not found in PATH.' >&2
  exit 1
fi

readonly COMPUTE_CAPABILITY="$(nvidia-smi -i 0 --query-gpu=compute_cap --format=csv,noheader | tr -d '[:space:]')"
if [[ "$COMPUTE_CAPABILITY" != '12.1' ]]; then
  echo "Warning: this recipe targets a GB10 (compute capability 12.1); detected ${COMPUTE_CAPABILITY}." >&2
fi

if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  echo "A container named '$CONTAINER_NAME' already exists." >&2
  echo "Remove or rename it explicitly before launching this recipe." >&2
  exit 1
fi

mkdir -p "$HF_CACHE"

docker_env_args=(--env 'HF_HOME=/root/.cache/huggingface')
if [[ -n "${HF_TOKEN:-}" ]]; then
  export HUGGING_FACE_HUB_TOKEN="${HUGGING_FACE_HUB_TOKEN:-$HF_TOKEN}"
  docker_env_args+=(--env HF_TOKEN --env HUGGING_FACE_HUB_TOKEN)
fi

# Do not force VLLM_USE_FLASHINFER_MOE_MXFP4_MXFP8 here. The upstream recipe
# enables it for SM100 datacenter Blackwell; GB10 is SM121 and needs vLLM to
# select an SM121-compatible MXFP4 backend.
docker run --detach \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --gpus all \
  --ipc host \
  --publish "${PORT}:8041" \
  --volume "${HF_CACHE}:/root/.cache/huggingface" \
  "${docker_env_args[@]}" \
  "$IMAGE" \
  "$MODEL" \
  --revision "$MODEL_REVISION" \
  --served-model-name "$SERVED_MODEL_NAME" \
  --host 0.0.0.0 \
  --port 8041 \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-num-batched-tokens "$MAX_NUM_BATCHED_TOKENS" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --kv-cache-dtype fp8 \
  --no-enable-prefix-caching \
  --max-cudagraph-capture-size 2048 \
  --stream-interval 20 \
  --enable-auto-tool-choice \
  --tool-call-parser openai

echo "Started $CONTAINER_NAME on port $PORT."
echo "Follow startup: docker logs --follow $CONTAINER_NAME"
echo "Wait for readiness: curl --fail http://localhost:${PORT}/v1/models"
