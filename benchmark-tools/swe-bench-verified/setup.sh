#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pins.env
source "$ROOT/pins.env"

clone_at_commit() {
  local url="$1"
  local destination="$2"
  local commit="$3"

  if [[ ! -d "$destination/.git" ]]; then
    git clone --filter=blob:none "$url" "$destination"
  fi
  git -C "$destination" fetch --filter=blob:none origin "$commit"
  git -C "$destination" checkout --detach "$commit"
  test "$(git -C "$destination" rev-parse HEAD)" = "$commit"
}

mkdir -p "$ROOT/vendor" "$ROOT/results" "$ROOT/manifests"

clone_at_commit \
  https://github.com/SWE-bench/SWE-bench.git \
  "$ROOT/vendor/SWE-bench" \
  "$SWEBENCH_COMMIT"

clone_at_commit \
  https://github.com/SWE-agent/SWE-agent.git \
  "$ROOT/vendor/SWE-agent" \
  "$SWEAGENT_COMMIT"

python3 -m venv "$ROOT/.venv-harness"
"$ROOT/.venv-harness/bin/python" -m pip install --upgrade pip setuptools wheel
"$ROOT/.venv-harness/bin/python" -m pip install -e "$ROOT/vendor/SWE-bench"

python3 -m venv "$ROOT/.venv-agent"
"$ROOT/.venv-agent/bin/python" -m pip install --upgrade pip setuptools wheel
"$ROOT/.venv-agent/bin/python" -m pip install -e "$ROOT/vendor/SWE-agent"

echo "Installed pinned SWE-bench and SWE-agent environments."
echo "No model inference, Docker image build, container, or evaluation was started."
