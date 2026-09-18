#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"
if [[ -f config.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source config.env
  set +a
fi
: "${RUN_DIR:?RUN_DIR must identify the result directory}"

mapfile -t aime_samples < <(find "$RUN_DIR/lm_eval/aime25" -type f -name 'samples_*.jsonl' 2>/dev/null | sort)
if [[ ${#aime_samples[@]} -eq 1 ]]; then
  .venv/bin/python scripts/score_aime.py "${aime_samples[0]}" \
    --output "$RUN_DIR/aime_rescore.json" >/dev/null
  printf 'Wrote %s\n' "$RUN_DIR/aime_rescore.json"
elif [[ ${#aime_samples[@]} -gt 1 ]]; then
  printf 'Expected one AIME sample file but found %s; refusing an ambiguous rescore.\n' \
    "${#aime_samples[@]}" >&2
  exit 6
else
  printf 'No AIME samples found; skipping robust rescore.\n' >&2
fi

if find "$RUN_DIR/lm_eval" -type f -name 'samples_*.jsonl' -print -quit 2>/dev/null | grep -q .; then
  .venv/bin/python scripts/audit_capability_outputs.py "$RUN_DIR"
else
  printf 'No capability samples found; skipping output-length audit.\n' >&2
fi
