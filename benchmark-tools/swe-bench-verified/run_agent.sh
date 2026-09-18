#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-}"
SCOPE="${2:-}"

usage() {
  echo "Usage: $0 <mode> <smoke|full>" >&2
  echo "Modes: qwen_off qwen_low qwen_medium qwen_xhigh mistral_none mistral_high nemotron_off nemotron_low nemotron_regular" >&2
  exit 2
}

[[ -n "$MODE" && -f "$ROOT/configs/modes/$MODE.yaml" ]] || usage
[[ "$SCOPE" == smoke || "$SCOPE" == full ]] || usage
[[ -f "$ROOT/endpoints.env" ]] || {
  echo "Missing $ROOT/endpoints.env; copy endpoints.env.example and configure it." >&2
  exit 3
}
# shellcheck source=/dev/null
source "$ROOT/endpoints.env"
export VLLM_API_KEY="${VLLM_API_KEY:-EMPTY}"

case "$MODE" in
  qwen_*) API_BASE="${QWEN_API_BASE:-}" ;;
  mistral_*) API_BASE="${MISTRAL_API_BASE:-}" ;;
  nemotron_*) API_BASE="${NEMOTRON_API_BASE:-}" ;;
  *) usage ;;
esac
[[ "$API_BASE" == http://*/v1 || "$API_BASE" == https://*/v1 ]] || {
  echo "The selected API base must be an http(s) URL ending in /v1." >&2
  exit 3
}
[[ "${SWE_BENCH_ACKNOWLEDGE_RUN:-}" == YES ]] || {
  echo "Refusing to run: set SWE_BENCH_ACKNOWLEDGE_RUN=YES intentionally." >&2
  exit 10
}
[[ -f "$ROOT/run-authorization" ]] || {
  echo "Refusing to run: $ROOT/run-authorization does not exist." >&2
  exit 10
}
if [[ "$SCOPE" == full ]]; then
  [[ "${SWE_BENCH_ACKNOWLEDGE_FULL_500:-}" == YES ]] || {
    echo "Refusing full run: set SWE_BENCH_ACKNOWLEDGE_FULL_500=YES." >&2
    exit 10
  }
fi

if [[ "$(uname -m)" != x86_64 && "${SWE_BENCH_ALLOW_ARM64_EXPERIMENTAL:-}" != YES ]]; then
  echo "Refusing to run on $(uname -m): official SWE-bench recommends x86_64." >&2
  exit 11
fi
docker info >/dev/null

DATASET="$ROOT/data/SWE-bench_Verified"
[[ -d "$DATASET" ]] || { echo "Pinned dataset is missing; run cache_verified_dataset.py." >&2; exit 12; }

slice_args=()
if [[ "$SCOPE" == smoke ]]; then
  slice_args=(--instances.slice :1)
fi

OUTPUT="$ROOT/results/$MODE/$SCOPE"
mkdir -p "$OUTPUT"

exec 9>"$ROOT/agent-run.lock"
flock -n 9 || { echo "Another SWE-agent run holds $ROOT/agent-run.lock" >&2; exit 13; }

exec "$ROOT/.venv-agent/bin/sweagent" run-batch \
  --config "$ROOT/vendor/SWE-agent/config/default.yaml" \
  --config "$ROOT/configs/agent_common.yaml" \
  --config "$ROOT/configs/modes/$MODE.yaml" \
  --agent.model.api_base "$API_BASE" \
  --instances.path_override "$DATASET" \
  --output_dir "$OUTPUT" \
  "${slice_args[@]}"
