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
base_url="${BASE_URL:-http://127.0.0.1:8000}"
api_key="${API_KEY:-EMPTY}"
model_id="${MODEL_ID:-}"

if [[ -z "$model_id" ]]; then
  model_id="$(BASE_URL="$base_url" API_KEY="$api_key" .venv/bin/python - <<'PY'
import json
import os
import urllib.request

request = urllib.request.Request(
    os.environ["BASE_URL"].rstrip("/") + "/v1/models",
    headers={"Authorization": "Bearer " + os.environ["API_KEY"]},
)
with urllib.request.urlopen(request, timeout=20) as response:
    model_ids = [item["id"] for item in json.load(response).get("data", [])]
if len(model_ids) != 1:
    raise SystemExit("Set MODEL_ID; endpoint must advertise exactly one model")
print(model_ids[0])
PY
)"
fi

export OPENAI_API_KEY="$api_key"
chat_url="${base_url%/}/v1/chat/completions"
catalog="$RUN_DIR/lm_eval_tasks.txt"
.venv/bin/lm-eval ls tasks > "$catalog"

read -r -a candidates <<< "${TASKS_OVERRIDE:-${EVAL_TASKS:-aime25 ifeval}}"
declare -a selected=()
for task in "${candidates[@]}"; do
  if grep -Eq "[|]${task}([[:space:]]|[|])" "$catalog"; then
    selected+=("$task")
  else
    printf 'SKIP unavailable task %s\n' "$task" | tee -a "$RUN_DIR/lm_eval_status.txt"
  fi
done

if [[ ${#selected[@]} -eq 0 ]]; then
  printf 'No requested tasks were found. See %s\n' "$catalog" >&2
  exit 5
fi

failed=0
for task in "${selected[@]}"; do
  output="$RUN_DIR/lm_eval/$task"
  mkdir -p "$output"
  printf 'Running one deterministic capability pass: %s\n' "$task"
  if .venv/bin/lm-eval run \
      --model local-chat-completions \
      --model_args "model=${model_id},base_url=${chat_url},api_key=${api_key},tokenized_requests=False,num_concurrent=${EVAL_CONCURRENCY:-4},max_retries=3,timeout=${EVAL_TIMEOUT:-21600},think_end_token=</think>" \
      --tasks "$task" \
      --apply_chat_template \
      --gen_kwargs "temperature=0,max_gen_toks=${MAX_GEN_TOKS:-130000}" \
      --log_samples \
      --output_path "$output"; then
    printf 'PASS %s\n' "$task" | tee -a "$RUN_DIR/lm_eval_status.txt"
  else
    printf 'FAIL %s\n' "$task" | tee -a "$RUN_DIR/lm_eval_status.txt"
    failed=1
  fi
done
exit "$failed"
