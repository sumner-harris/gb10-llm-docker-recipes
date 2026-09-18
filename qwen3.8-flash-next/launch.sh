#!/usr/bin/env bash
set -Eeuo pipefail

# Exact image and checkpoint used by the validated single-GB10 MTP=2 service.
# Human-readable image tag: nightly-8a728663c1c3eeace834a95f5654fa653cc1998c
readonly IMAGE='vllm/vllm-openai@sha256:f5df5cc3302b5f404848c4eca88d7bf7ed5226e151c056da22816d7734644d67'
readonly MODEL='nvidia/Qwen3.8-Flash-Next-NVFP4'
readonly MODEL_REVISION='fc694b54fb0174e0913e6adf86691ef85a4ead47'
readonly SERVED_MODEL_NAME='qwen3.8-flash-next'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PATCH_DIR="${PATCH_DIR:-$SCRIPT_DIR/patches}"
MODEL_DIR="${MODEL_DIR:-$HOME/hf_cache/Qwen3.8-Flash-Next-NVFP4-nvidia}"
CACHE_DIR="${CACHE_DIR:-/var/tmp/qwen38fn-vllm-cache}"
CONTAINER_NAME="${CONTAINER_NAME:-vllm_qwen38fn}"
PORT="${PORT:-8000}"
MTP="${MTP:-2}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-262144}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-6}"
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-4096}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.80}"
PLE_THREADS="${PLE_THREADS:-64}"
DRAFT_VOCAB="${DRAFT_VOCAB:-65536}"

for integer in "$PORT" "$MTP" "$MAX_MODEL_LEN" "$MAX_NUM_SEQS" \
  "$MAX_NUM_BATCHED_TOKENS" "$PLE_THREADS" "$DRAFT_VOCAB"; do
  [[ "$integer" =~ ^[0-9]+$ ]] || {
    echo "Expected a positive integer, got: $integer" >&2
    exit 2
  }
done
(( PORT >= 1 && PORT <= 65535 )) || { echo "Invalid PORT: $PORT" >&2; exit 2; }
(( MTP >= 1 && MTP <= 10 )) || { echo "MTP must be from 1 through 10." >&2; exit 2; }
(( MAX_NUM_SEQS >= 1 )) || { echo "MAX_NUM_SEQS must be positive." >&2; exit 2; }

[[ -f "$MODEL_DIR/config.json" ]] || {
  echo "Model is missing at $MODEL_DIR" >&2
  echo "Download $MODEL at revision $MODEL_REVISION to that local NVMe path." >&2
  exit 3
}

metadata_file="$(find "$MODEL_DIR/.cache/huggingface/download" -maxdepth 1 \
  -type f -name '*.metadata' -print -quit 2>/dev/null || true)"
if [[ -n "$metadata_file" ]]; then
  actual_revision="$(head -n 1 "$metadata_file")"
  [[ "$actual_revision" == "$MODEL_REVISION" ]] || {
    echo "Model revision mismatch: expected $MODEL_REVISION, found $actual_revision" >&2
    exit 3
  }
elif [[ "${SKIP_MODEL_REVISION_CHECK:-0}" != 1 ]]; then
  echo "Cannot verify the model revision: Hugging Face metadata is absent." >&2
  echo "Set SKIP_MODEL_REVISION_CHECK=1 only after independently verifying it." >&2
  exit 3
fi

(cd "$SCRIPT_DIR" && sha256sum --check --strict patches/SHA256SUMS)

if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  echo "A container named '$CONTAINER_NAME' already exists." >&2
  echo "Remove or rename it explicitly before launching this recipe." >&2
  exit 1
fi

mkdir -p "$CACHE_DIR"

stride=$((MTP + 1))
capture_sizes=''
for ((sequence = 1; sequence <= MAX_NUM_SEQS; sequence++)); do
  [[ -z "$capture_sizes" ]] || capture_sizes+=','
  capture_sizes+=$((stride * sequence))
done

readonly VLLM_ROOT='/usr/local/lib/python3.12/dist-packages/vllm'
readonly SPECULATIVE_CONFIG="$(printf \
  '{"method":"mtp","num_speculative_tokens":%d}' "$MTP")"
readonly COMPILATION_CONFIG="$(printf \
  '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[%s]}' \
  "$capture_sizes")"

docker run --detach \
  --name "$CONTAINER_NAME" \
  --restart no \
  --gpus all \
  --network host \
  --ipc host \
  --shm-size 32g \
  --ulimit memlock=-1:-1 \
  --volume "$MODEL_DIR:/models/qwen38fn:ro" \
  --volume "$CACHE_DIR:/root/.cache" \
  --volume "$PATCH_DIR/ple_layer.py:$VLLM_ROOT/models/qwen4_exp/nvidia/ple_layer.py:ro" \
  --volume "$PATCH_DIR/ple_mmap.py:$VLLM_ROOT/models/qwen4_exp/nvidia/ops/ple_mmap.py:ro" \
  --volume "$PATCH_DIR/model_state.py:$VLLM_ROOT/models/qwen4_exp/nvidia/model_state.py:ro" \
  --volume "$PATCH_DIR/mtp_draft_vocab.py:$VLLM_ROOT/models/qwen4_exp/nvidia/mtp.py:ro" \
  --volume "$PATCH_DIR/qsa_cache.py:$VLLM_ROOT/models/qwen4_exp/common/qsa_cache.py:ro" \
  --volume "$PATCH_DIR/upstream-overlays/ops_ple.py:$VLLM_ROOT/models/qwen4_exp/nvidia/ops/ple.py:ro" \
  --volume "$PATCH_DIR/upstream-overlays/ops_qsa.py:$VLLM_ROOT/models/qwen4_exp/nvidia/ops/qsa.py:ro" \
  --volume "$PATCH_DIR/upstream-overlays/qsa.py:$VLLM_ROOT/models/qwen4_exp/nvidia/qsa.py:ro" \
  --volume "$PATCH_DIR/upstream-overlays/platforms_interface.py:$VLLM_ROOT/platforms/interface.py:ro" \
  --volume "$PATCH_DIR/upstream-overlays/modelopt.py:$VLLM_ROOT/model_executor/layers/quantization/modelopt.py:ro" \
  --env HF_HUB_OFFLINE=1 \
  --env TRANSFORMERS_OFFLINE=1 \
  --env VLLM_ENGINE_READY_TIMEOUT_S=3600 \
  --env PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  --env CUTE_DSL_ARCH=sm_121a \
  --env TORCH_CUDA_ARCH_LIST=12.1a \
  --env FLASHINFER_CUDA_ARCH_LIST=12.1a \
  --env FLASHINFER_DISABLE_VERSION_CHECK=1 \
  --env VLLM_USE_DEEP_GEMM=0 \
  --env VLLM_USE_V2_MODEL_RUNNER=1 \
  --env QWEN4EXP_PLE_MMAP=1 \
  --env QWEN4EXP_PLE_STAGED=1 \
  --env QWEN4EXP_PLE_MMAP_THREADS="$PLE_THREADS" \
  --env QWEN4EXP_DRAFT_VOCAB="$DRAFT_VOCAB" \
  "$IMAGE" \
  /models/qwen38fn \
  --served-model-name "$SERVED_MODEL_NAME" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --trust-remote-code \
  --quantization modelopt \
  --tensor-parallel-size 1 \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --max-num-batched-tokens "$MAX_NUM_BATCHED_TOKENS" \
  --no-enable-flashinfer-autotune \
  --no-enable-prefix-caching \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml \
  --default-chat-template-kwargs '{"enable_thinking":false}' \
  --speculative-config "$SPECULATIVE_CONFIG" \
  --compilation-config "$COMPILATION_CONFIG" \
  --kv-cache-dtype fp8_e4m3

echo "Started $CONTAINER_NAME with MTP=$MTP and capture sizes [$capture_sizes]."
echo "Weights can take about 10 minutes to load."
echo "Wait for readiness: curl --fail http://localhost:${PORT}/v1/models"
