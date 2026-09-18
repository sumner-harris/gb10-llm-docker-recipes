#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
if [[ -f config.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source config.env
  set +a
fi

run_id="$(date -u +%Y%m%dT%H%M%SZ)"
export RUN_DIR="${RUN_DIR:-${RESULTS_DIR:-results}/${run_id}}"
mkdir -p "$RUN_DIR"

.venv/bin/python scripts/probe_endpoint.py | tee "$RUN_DIR/probe.json"

capability_failed=0
if ! bash scripts/run_lm_eval.sh; then
  capability_failed=1
fi
if ! bash scripts/run_gpqa.sh; then
  capability_failed=1
fi
bash scripts/postprocess_capability.sh
.venv/bin/python scripts/run_perf.py

printf 'Completed artifacts are in %s\n' "$RUN_DIR"
if [[ "$capability_failed" -ne 0 ]]; then
  printf 'At least one capability task failed; inspect lm_eval_status.txt.\n' >&2
  exit 1
fi
