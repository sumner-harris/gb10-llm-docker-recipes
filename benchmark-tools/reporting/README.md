# Benchmark publication tools

This directory contains deterministic builders for the repository's uniform
benchmark reports. Published CSV and JSON are the source of truth; plots and
Markdown summarize those same rows.

Install the plotting dependencies with
`python -m pip install -r benchmark-tools/reporting/requirements.txt`.

Every structured report uses `schema_version`, `benchmark_type`, `status`,
`model`, `hardware`, `runtime`, `workload`, `selection_rule`, `limitations`,
`summary_rows`, and `per_repeat_rows` as its common top-level contract.

## Speculative decoding

`build_qwen_mtp_report.py` converts the retained Qwen MTP 1–10 cell tree into
the standard nine-file report. It publishes aggregate metrics and hashes only;
raw prompts and model responses remain outside the repository.

```bash
python benchmark-tools/reporting/build_qwen_mtp_report.py \
  /path/to/mtp1_10_speedbench_20260912 \
  qwen3.8-flash-next/benchmarks/2026-09-12-mtp-sweep
```

For new benchmarks, follow `AGENTS.md`. Comparison reports and parameter sweeps
use the same filenames and metric names. A parameter sweep must set
`benchmark_type=speculative_parameter_sweep` and must not report speedup unless
an MTP-off baseline was measured in the same workload matrix.

`normalize_speculative_reports.py` rebuilds the Mistral and Nemotron structured
reports in the same top-level schema and replaces private absolute source paths
with sanitized retained-result provenance. It does not alter measured values.

## Responses API throughput matrix

`build_responses_throughput_report.py` converts a complete retained
`benchmark_speed_responses.py` cell tree into the standard CSV/JSON, Markdown,
and five-plot artifact set without publishing raw prompts, responses, private
endpoints, or absolute paths.

```bash
python benchmark-tools/reporting/build_responses_throughput_report.py \
  benchmark-tools/openai-compatible-suite/results/gpt-oss-120b-mxfp4-20260924-responses/baseline \
  gpt-oss-120b-mxfp4/benchmarks/2026-09-24-throughput-matrix
```

## Capability chart

Add audited rows to `benchmark-results/capability/scores.csv`, then run:

```bash
python benchmark-tools/reporting/render_capability_chart.py \
  benchmark-results/capability/scores.csv \
  benchmark-results/capability/capability-comparison.png
```

The renderer intentionally rejects an empty dataset and excludes every row not
marked `PASS`. Do not chart reference-only, capped, partial, or provisional
scores.
