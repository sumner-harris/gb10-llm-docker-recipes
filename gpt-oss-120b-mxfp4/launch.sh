#!/usr/bin/env bash
set -Eeuo pipefail

# Known-good artifacts elsewhere in this repository use this ARM64-capable
# Ubuntu 24.04 image. The comment retains its human-readable tag.
# vLLM tag: vllm/vllm-openai:v0.28.0-ubuntu2404
readonly IMAGE='vllm/vllm-openai@sha256:f8fe15a8039343336945db10494eaad80ef941fe2b2a5fa6649fa38636051a65'
readonly MODEL='openai/gpt-oss-120b'
readonly MODEL_REVISION='b5c939de8f754692c1647ca79fbf85e8c1e70f8a'
readonly SERVED_MODEL_NAME='gpt-oss-120b-mxfp4'
readonly O200K_URL='https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken'
readonly O200K_SHA256='446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d'
readonly CL100K_URL='https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken'
readonly CL100K_SHA256='223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7'

CONTAINER_NAME="${CONTAINER_NAME:-vllm-gpt-oss-120b-mxfp4}"
PORT="${PORT:-8041}"
HF_CACHE="${HF_CACHE:-$HOME/hf_cache}"
TIKTOKEN_CACHE="${TIKTOKEN_CACHE:-$HF_CACHE/tiktoken_encodings}"
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

mkdir -p "$HF_CACHE" "$TIKTOKEN_CACHE"

download_encoding() {
  local filename="$1"
  local url="$2"
  local expected_sha256="$3"
  local destination="$TIKTOKEN_CACHE/$filename"
  local temporary="${destination}.tmp.$$"

  if [[ -f "$destination" ]] && printf '%s  %s\n' "$expected_sha256" "$destination" | sha256sum --check --status; then
    return
  fi

  rm -f "$temporary"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --retry 3 --output "$temporary" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget --tries=3 --output-document="$temporary" "$url"
  else
    echo 'curl or wget is required to download the GPT-OSS tiktoken encodings.' >&2
    exit 1
  fi

  if ! printf '%s  %s\n' "$expected_sha256" "$temporary" | sha256sum --check --status; then
    rm -f "$temporary"
    echo "SHA-256 verification failed for $filename." >&2
    exit 1
  fi
  mv -f "$temporary" "$destination"
}

# openai-harmony loads these vocabularies when the first generation request is
# rendered. Pre-fetching them avoids a healthy-looking server that later returns
# HTTP 500 when the container cannot reach the public encoding store.
download_encoding 'o200k_base.tiktoken' "$O200K_URL" "$O200K_SHA256"
download_encoding 'cl100k_base.tiktoken' "$CL100K_URL" "$CL100K_SHA256"

docker_env_args=(
  --env 'HF_HOME=/root/.cache/huggingface'
  --env 'TIKTOKEN_ENCODINGS_BASE=/root/.cache/tiktoken_encodings'
)
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
  --volume "${TIKTOKEN_CACHE}:/root/.cache/tiktoken_encodings:ro" \
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
