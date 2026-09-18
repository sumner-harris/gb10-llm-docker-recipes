#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PREDICTIONS="${1:-}"
RUN_ID="${2:-}"
WORKERS="${SWE_BENCH_EVAL_WORKERS:-8}"

[[ -f "$PREDICTIONS" && -n "$RUN_ID" ]] || {
  echo "Usage: $0 <predictions.jsonl> <unique-run-id>" >&2
  exit 2
}
[[ "${SWE_BENCH_ACKNOWLEDGE_EVALUATION:-}" == YES ]] || {
  echo "Refusing to evaluate: set SWE_BENCH_ACKNOWLEDGE_EVALUATION=YES." >&2
  exit 10
}
[[ -f "$ROOT/run-authorization" ]] || {
  echo "Refusing to evaluate: $ROOT/run-authorization does not exist." >&2
  exit 10
}
[[ "$(uname -m)" == x86_64 ]] || {
  echo "Refusing scored evaluation on $(uname -m); use an x86_64 Docker worker." >&2
  exit 11
}
docker info >/dev/null

exec 9>"$ROOT/evaluation.lock"
flock -n 9 || { echo "Another evaluation holds $ROOT/evaluation.lock" >&2; exit 13; }

exec "$ROOT/.venv-harness/bin/python" -m swebench.harness.run_evaluation \
  --dataset_name "$ROOT/data/SWE-bench_Verified" \
  --split test \
  --predictions_path "$PREDICTIONS" \
  --max_workers "$WORKERS" \
  --cache_level env \
  --run_id "$RUN_ID"
