# Agent guide: reproducible benchmark publication

This file applies to the entire repository. Use it whenever adding or updating
a model recipe, running a throughput comparison, or publishing benchmark
artifacts. The goal is that a different agent can repeat the experiment and
produce the same class of report without relying on chat history.

The canonical published examples are:

- `qwen3.8-flash-next/benchmarks/2026-09-12-mtp-sweep/`
- `mistral-small-4-119b-nvfp4/benchmarks/2026-09-17-eagle-comparison/`
- `nemotron-3-super-120b-nvfp4/benchmarks/2026-09-17-mtp-comparison/`

## Required reporting workflow for agents

Before publishing, classify the run as exactly one of:

- `speculative_comparison`: the same model/workload includes a no-speculation
  baseline and one or more speculative variants.
- `speculative_parameter_sweep`: only speculative settings are compared. Never
  call a parameter sweep a speedup or uplift measurement.
- `capability`: task accuracy or instruction-following scores, separated by an
  explicitly captured reasoning mode.

Use the standard artifact names below, keep full precision in CSV/JSON, round
only Markdown/plot labels, and derive every prose claim and plot from the
machine-readable rows. Reports must lead with status, scope, sample count,
winner/selection, and the most important limitation in that order. Do not make
readers infer whether a baseline exists, whether a result is capped, or whether
the reasoning mode was implicit.

Every model-local report belongs under `<model>/benchmarks/`. Add the report to
the model README and add one compact row to the root README. Never put raw
prompt/response text, private endpoints, credentials, or absolute host paths in
a publication.

## Non-negotiable safety rules

1. Preserve a working deployment before changing it. Record its container
   inspect data, image identity/digest, command, mounts, environment-variable
   names, logs, and current API health. Never store secret values.
2. Stop the original container when GPU memory must be released; do not remove
   it. Give every benchmark container a different name.
3. Pin the serving image by registry digest and every Hugging Face checkpoint by
   commit revision. Record human-readable tags separately.
4. Use a rollback trap or equivalent cleanup path. If a candidate fails, remove
   only the candidate container and restart the preserved original.
5. A running container is not a ready server. Wait for `GET /v1/models`, verify
   the advertised model and maximum context, and then send a real
   `POST /v1/responses` request.
6. Do not commit tokens, passwords, private IPs, absolute user paths, raw Docker
   environments, or unsanitized container-inspect output.
7. Never report a failed, timed-out, or partially recovered cell as successful.
   Quarantine it, explain it, and rerun the complete cell after a clean restart.

## Deployment comparison rules

Change only the setting under test. Keep the image, target checkpoint, model
revision, API settings, model length, batch limits, cache types, attention
backend, parsers, and workload constant. Document every unavoidable exception.
For example, Nemotron's external MTPv2 head needs GPU-memory utilization `0.82`
instead of `0.80` to preserve the 131,072-token context; this exception belongs
in both the recipe and benchmark report.

Give variants stable machine-readable names such as `baseline`, `eagle1`,
`eagle3`, `builtin_mtp3`, or `mtpv2_mtp3`. Also give each a readable label for
tables and plots. Save the exact launch command or speculative configuration for
every variant.

Before measuring a variant, verify from vLLM startup logs that it loaded the
intended target and draft checkpoints, revisions, draft-token count, backend,
model length, and KV-cache allocation. For speculative runs, verify after a
request that the Prometheus draft and accepted-token counters increase.

## Canonical Responses API workload

Use the retained `benchmark_speed_responses.py` runner when available. Its
workload contract is part of the result and must not be silently changed:

- OpenAI-compatible streaming `POST /v1/responses` API.
- Ten fixed prompts: nine deterministically selected NVIDIA SPEED-Bench
  `throughput_2k` prompts plus `tell me a 1000 word story`.
- The selected dataset file has SHA-256
  `96765a32a67a83f07ddded74cfd5639a7c2afd1a1ff0f3c244b1cff0a9732f3b`.
- Maximum output: 512 tokens.
- Closed-loop concurrency levels: 1, 2, 4, and 6.
- Reasoning efforts: all model-native modes actually supported by the model.
  Qwen3.8-Flash-Next uses OFF, `low`, `medium`, and `xhigh`; Mistral Small 4
  uses `none` and `high`; Nemotron-3 Super uses reasoning-off, low-effort
  reasoning, and regular reasoning. Never copy one model's mode list to another.
- Two excluded warmup batches before every concurrency level, using effort
  `none` and a 128-token output limit.
- Keep recorded prompts exact; do not add nonce text unless the experiment is
  specifically meant to defeat prefix caching.
- Use explicit `reasoning: {"effort":"none"}` where supported. If a model does
  not support configurable reasoning, use only `none` and omit the field.
- Collect vLLM Prometheus metrics. Sample `nvidia-smi` only when the benchmark
  runner is on the inference host; remote client-side GPU samples are invalid.

The runner is not currently vendored in this recipes repository. If it is not
available in the benchmark workspace, obtain an audited copy or implement the
contract above and the raw result schema below. Do not substitute a generic
load tester whose timing, token accounting, or concurrency semantics differ.

Use three measured repeats per cell for a new publication when time permits.
One complete repeat is acceptable for an expensive sweep, but state that fact
prominently and do not present a one-sample range as uncertainty. Never claim
three-repeat medians for a one-repeat matrix.

A standard invocation is:

```bash
python benchmark_speed_responses.py \
  nemotron-3-super-120b-nvfp4 http://127.0.0.1:8031/v1 \
  --run-label mtpv2_mtp3 \
  --dataset speed_bench_throughput_2k_selected.json \
  --efforts none,low,high \
  --concurrencies 1,2,4,6 \
  --repeats 3 \
  --warmup-batches 2 \
  --warmup-effort none \
  --warmup-max-output-tokens 128 \
  --max-output-tokens 512 \
  --none-mode explicit \
  --metrics-url auto \
  --output-dir benchmark_results/nemotron3_super/mtpv2_mtp3
```

Use `--resume` only when the server configuration and dataset are unchanged.
Do not combine cells produced by different image digests, checkpoint revisions,
launch arguments, or workload files.

## Reasoning-mode terminology and proof

Show a friendly model-native name and separately record the exact wire fields.
The current canonical mappings are:

| Model | Display mode | Required explicit controls |
| --- | --- | --- |
| Qwen3.8-Flash-Next | OFF | `reasoning_effort=none`, `enable_thinking=false`, `preserve_thinking=false` |
| Qwen3.8-Flash-Next | low / medium / xhigh | matching `reasoning_effort`, `enable_thinking=true`, `preserve_thinking=false` |
| Mistral Small 4 | none / high | matching explicit `reasoning_effort` |
| Nemotron-3 Super | reasoning-off | `reasoning_effort=none`, `enable_thinking=false`, `low_effort=false` |
| Nemotron-3 Super | low-effort reasoning | `reasoning_effort=low`, `enable_thinking=true`, `low_effort=true` |
| Nemotron-3 Super | regular reasoning | transport alias `reasoning_effort=high`, `enable_thinking=true`, `low_effort=false` |

Capture the exact outbound JSON for every capability sample and at least one
auditable request for every performance cell. Do not infer the active mode from
a server default or label. If exact outbound evidence is missing, label the run
`reference-only` and keep it out of cross-model charts.

## Raw result contract

Keep the complete local result tree until publication is validated. A variant
directory normally contains:

```text
variant/
  run_config.json
  container-inspect.json       # local and access-restricted; sanitize if shared
  startup.log                  # local; publish only when scrubbed and useful
  benchmark_matrix.csv
  benchmark_requests.csv       # local by default; may contain prompt/output text
  benchmark_report.json
  cells/
    <effort>_c<concurrency>_r<repeat>.json
  complete
```

Write each cell atomically as it finishes so an interruption is resumable. Keep
quarantined failed attempts outside the valid cell path for auditability. The
publication is derived from valid cell files, not from console output or copied
numbers.

## Metric definitions

Use these definitions consistently in CSV, JSON, Markdown, and plot labels:

- **System output tokens/s**: total successful output tokens divided by the
  measured cell wall time. This is the primary server-capacity metric.
- **Request throughput**: successful requests divided by cell wall time.
- **TTFT**: request start to the first non-empty streamed reasoning or answer
  text delta. Report at least the per-cell p50.
- **First-answer latency (TTFO)**: request start to the first non-reasoning
  answer-text delta. Responses that hit the token cap before answer text do not
  have TTFO.
- **Visible-answer rate**: successful responses with a TTFO divided by all
  successful responses.
- **Reasoning share**: reasoning output tokens divided by all output tokens.
- **Draft acceptance**: accepted speculative tokens divided by proposed draft
  tokens, calculated from server metric deltas.
- **Mean accepted length**: `1 + accepted_draft_tokens / draft_steps`.
- **Speedup vs baseline**: candidate system output tokens/s divided by the
  baseline from the same effort, concurrency, and repeat. For a summary table,
  compare the corresponding repeat medians.

Configuration-wide means give each measured effort/concurrency cell equal
weight. Configuration-wide acceptance must be weighted from summed counters:

```text
weighted_acceptance = sum(accepted_draft_tokens) / sum(draft_tokens)
weighted_mean_accepted_length = 1 + sum(accepted_draft_tokens) / sum(draft_steps)
```

Do not average already-rounded percentages. Preserve full precision in CSV and
JSON; round only human-readable Markdown and plot annotations.

## Required publication artifacts

Publish under:

```text
<recipe>/benchmarks/YYYY-MM-DD-<method>-comparison/
```

The directory must contain the same artifact set as the canonical reports:

```text
README.md
comparison_summary.csv
comparison_by_repeat.csv
comparison_report.json
throughput_comparison.png
ttft_comparison.png
first_answer_latency_comparison.png
acceptance_comparison.png
reasoning_share_comparison.png
```

`comparison_by_repeat.csv` contains one row per valid measured cell and uses
repo-relative provenance such as `mtpv2_mtp3/cells/low_c4_r1.json`. The JSON
contains both the per-repeat rows and summarized rows. Do not include raw prompt
or response text in the publication unless explicitly requested and licensed.

The report `README.md` must include:

1. Exact measured request and cell counts, repeat count, and success count.
2. All five plots embedded with relative links.
3. Links to the two CSVs and structured JSON.
4. A cell-by-cell table with effort, variant, concurrency, throughput, baseline
   delta, TTFT, first-answer latency, visible-answer rate, reasoning share, and
   draft acceptance.
5. A plain-language conclusion that names the winner and quantifies tradeoffs.
6. Workload, warmup, concurrency, output-token, and reasoning settings.
7. Why the speculative method was chosen and the exact speculative-config JSON.
8. All material launch differences and any compatibility patches.
9. Preservation/rollback actions and the final validated service state.

For four reasoning levels, use a 2x2 panel for each plot. For two levels, use a
1x2 layout. Use the same variant colors in every plot. Show repeat ranges or
error bars only when multiple repeats exist. Visually inspect every rendered
image before committing it.

Link the dated report from the recipe's top-level `README.md`. Compact aggregate
CSVs may also be published, but they do not replace the dated report above.

For large parameter sweeps, the Markdown table may summarize one row per
variant while `comparison_by_repeat.csv` retains every effort/concurrency cell.
Use `benchmark_type=speculative_parameter_sweep`, make the lack of a baseline
prominent, and set baseline-relative fields to null/blank rather than inventing
a reference. Use the standard five plot names even when variants are on the
x-axis and concurrency is the plotted series.

## Capability publication and main-page chart

Publish each capability mode under
`<model>/benchmarks/YYYY-MM-DD-capability-<mode>/`. It must contain a README,
structured task summary, retained sample/provenance files or hashes, generation
and harness metadata, and model-local plots. Then append normalized rows to
`benchmark-results/capability/scores.csv`.

Required score-row fields are defined in that CSV header. Use 0–1 scores and
canonical metric IDs (`aime25_accuracy`, `gpqa_diamond_accuracy`,
`ifeval_prompt_strict`, and `ifeval_instruction_strict`). A chartable row must:

1. have `result_status=PASS`;
2. link to a model-local dated report;
3. record the exact wire reasoning effort and friendly mode name;
4. record sample counts, temperature, seed, generation cap, harness, and task
   revision;
5. have no missing, empty, placeholder, timed-out, or length-capped response.

After validating the CSV, run
`benchmark-tools/reporting/render_capability_chart.py`. The required output is
the grouped vertical bar chart
`benchmark-results/capability/capability-comparison.png`, embedded on the root
README by replacing its `CAPABILITY_CHART` placeholder. Never plot provisional,
reference-only, capped, or differently-versioned task results as if they were
directly comparable.

## Validation before commit

Complete every check below:

1. Parse all JSON and CSV artifacts programmatically.
2. Assert the expected cell count: `efforts × concurrencies × repeats × variants`.
3. Assert that every published cell has ten requests, ten successes, and zero
   errors unless the report explicitly defines another workload size.
4. Recompute configuration means, speedups, weighted acceptance, and accepted
   length from the per-repeat rows; compare them with the Markdown claims.
5. Verify generated artifacts came from the retained source files, preferably
   with SHA-256 hashes before and after copying.
6. Scan staged benchmark artifacts for `hf_`, credential assignments,
   passwords, API keys, private IPs, `/home/`, and `C:\\Users\\`. Literal
   environment-variable names in this policy file are expected; secret values
   are never allowed. Replace absolute `source_file` paths with repo-relative
   paths.
7. Open all plots and check titles, legends, axes, units, missing values, and
   readability at GitHub's rendered size.
8. Run `git diff --cached --check`, review the complete staged diff, and ensure
   unrelated worktree changes are not staged.
9. Push the commit, confirm local `HEAD` matches the remote branch, and provide
   links to the dated report and commit.

## Reporting integrity

Never infer throughput from a smoke test, mix screen-run cells with a full
matrix without labeling them, discard an unfavorable valid result, or silently
change the workload between variants. If the evidence is incomplete, publish
the limitation or rerun the missing cells. The machine-readable artifacts are
the source of truth; prose and plots must be reproducible from them.
