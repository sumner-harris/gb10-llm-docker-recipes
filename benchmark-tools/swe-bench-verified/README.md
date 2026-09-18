# SWE-bench Verified local-model campaign

This reusable tool pins the official SWE-bench evaluator, official SWE-agent, and
the 500-task SWE-bench Verified dataset. It is configured for the three local
OpenAI-compatible vLLM deployments and every supported explicit reasoning
mode.

Nothing in `setup.sh` or `validate_setup.py` performs inference, starts an
evaluation container, or queues a run. `run_agent.sh` and
`evaluate_predictions.sh` both require explicit acknowledgment variables.

## Pinned components

- SWE-bench: `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`
- SWE-agent: `3ea751c087f32b16e039a2233dd6eefecef325d5`
- `SWE-bench/SWE-bench_Verified` dataset:
  `78f471bf655a3137b2e8a75af1501690ec009ec3`
- Split: all 500 `test` instances
- Agent: SWE-agent `config/default.yaml`, with only documented local-model
  compatibility overrides and explicit reasoning controls
- Grader: official Docker-based SWE-bench evaluation harness

The agent uses the official default prompt and tools. Prompt caching is removed
because the local endpoints do not use Anthropic cache-control message blocks.
Function calling remains enabled. Every model call is temperature 0, seed 1234,
and explicitly sets the model-native reasoning controls. Cost limits are
disabled for local inference and each issue is limited to 100 model calls.

## Host requirements

SWE-agent explicitly selects the
official `linux/amd64` SWE-bench task images, and the official evaluator
recommends x86-64 while describing ARM64 support as experimental. The guarded
run scripts therefore refuse to run on ARM64 by default. Use an x86-64 Linux
Docker host with at least 120 GB free storage, 16 GB RAM, and 8 CPU cores for
the scored campaign. Do not bypass the architecture gate for a published
comparison.

The model endpoints may remain on the GB10 systems; only the agent/task Docker
environment and final grading need the x86-64 worker to be able to reach those
endpoints.

## Prepared modes

| Config | Model-native mode | Explicit controls |
| --- | --- | --- |
| `qwen_off` | OFF | `none`, thinking false, preserve false |
| `qwen_low` | low | `low`, thinking true, preserve false |
| `qwen_medium` | medium | `medium`, thinking true, preserve false |
| `qwen_xhigh` | xhigh | `xhigh`, thinking true, preserve false |
| `mistral_none` | none | `none` |
| `mistral_high` | high | `high` |
| `nemotron_off` | reasoning-off | `none`, thinking false, low-effort false |
| `nemotron_low` | low-effort reasoning | `low`, thinking true, low-effort true |
| `nemotron_regular` | regular reasoning | transport alias `high`, thinking true, low-effort false |

## Setup and validation (does not run the benchmark)

```bash
./setup.sh
.venv-harness/bin/python scripts/cache_verified_dataset.py
cp endpoints.env.example endpoints.env
# Edit only the ignored endpoints.env with reachable API bases and any key.
.venv-agent/bin/python scripts/validate_setup.py
```

Validation checks repository pins, the dataset revision/count/IDs, all nine
mode configurations, explicit reasoning fields, Docker availability,
architecture, and the absence of an authorization sentinel. It does not send
completion requests. Before a future run, verify each configured endpoint with
`GET /v1/models` and confirm its advertised ID matches the relevant mode file.

## Deliberately guarded execution

Before a future smoke test, use an x86-64 Docker worker that can reach the
configured model endpoints. Then intentionally create the authorization
sentinel and acknowledge the run:

```bash
touch run-authorization
SWE_BENCH_ACKNOWLEDGE_RUN=YES ./run_agent.sh qwen_off smoke
```

The smoke mode runs one Verified task and is never included in the published
score. A complete 500-task pass additionally requires a second acknowledgment:

```bash
SWE_BENCH_ACKNOWLEDGE_RUN=YES \
SWE_BENCH_ACKNOWLEDGE_FULL_500=YES \
./run_agent.sh qwen_off full
```

There is no campaign supervisor and no automatic mode chaining. Each mode must
be started deliberately after confirming the endpoint is otherwise idle.

After SWE-agent produces `preds.json`, convert it to the official prediction
JSONL format and run the pinned evaluator on an x86-64 Docker worker:

```bash
.venv-harness/bin/python scripts/convert_predictions.py \
  results/qwen_off/full/preds.json \
  results/qwen_off/full/predictions.jsonl

SWE_BENCH_ACKNOWLEDGE_EVALUATION=YES \
./evaluate_predictions.sh \
  results/qwen_off/full/predictions.jsonl \
  qwen_off_full_001
```

Always use a new `run_id` when the prediction file changes; the official
harness caches results by instance and run ID, not by patch content.
