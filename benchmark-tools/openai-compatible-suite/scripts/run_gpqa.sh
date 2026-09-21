#!/usr/bin/env bash
set -uo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"
if [[ -f config.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source config.env
  set +a
fi
: "${RUN_DIR:?RUN_DIR must identify the result directory}"

mode="${RUN_GPQA:-auto}"
task="${GPQA_TASK:-gpqa_diamond_cot_zeroshot}"
status_file="$RUN_DIR/gpqa_access.json"

if [[ "$task" != "gpqa_diamond_cot_zeroshot" ]]; then
  printf 'ERROR GPQA task must be gpqa_diamond_cot_zeroshot, got %s\n' "$task" \
    | tee -a "$RUN_DIR/lm_eval_status.txt" >&2
  exit 2
fi
if [[ "$mode" == "0" || "$mode" == "false" || "$mode" == "disabled" ]]; then
  printf 'SKIP GPQA disabled by RUN_GPQA=%s\n' "$mode" \
    | tee -a "$RUN_DIR/lm_eval_status.txt"
  exit 0
fi
if [[ "$mode" != "auto" && "$mode" != "1" && "$mode" != "true" ]]; then
  printf 'ERROR RUN_GPQA must be auto, 1, true, 0, false, or disabled\n' \
    | tee -a "$RUN_DIR/lm_eval_status.txt" >&2
  exit 2
fi

.venv/bin/python scripts/check_gpqa_access.py "$status_file"
access_status=$?
if [[ "$access_status" -eq 10 ]]; then
  printf 'BLOCKED %s: official dataset authentication/license access required; see %s\n' \
    "$task" "$status_file" | tee -a "$RUN_DIR/lm_eval_status.txt"
  exit 0
fi
if [[ "$access_status" -ne 0 ]]; then
  printf 'ERROR %s: access check failed; see %s\n' "$task" "$status_file" \
    | tee -a "$RUN_DIR/lm_eval_status.txt" >&2
  exit "$access_status"
fi

printf 'Running official gated GPQA task %s\n' "$task"
TASKS_OVERRIDE="$task" bash scripts/run_lm_eval.sh
task_status=$?
if [[ "$task_status" -ne 0 ]]; then
  printf 'FAIL %s: lm-eval exited with status %s\n' "$task" "$task_status" \
    | tee -a "$RUN_DIR/lm_eval_status.txt" >&2
  exit "$task_status"
fi

# Retain lm-eval's native metric, but report GPQA with the explicit-final-answer
# AA-compatible extractor to avoid the last-parenthesized-letter failure mode.
.venv/bin/python scripts/score_gpqa_robust.py "$RUN_DIR"
score_status=$?
if [[ "$score_status" -ne 0 ]]; then
  printf 'FAIL %s: robust GPQA scoring exited with status %s\n' "$task" "$score_status" \
    | tee -a "$RUN_DIR/lm_eval_status.txt" >&2
  exit "$score_status"
fi
exit 0
