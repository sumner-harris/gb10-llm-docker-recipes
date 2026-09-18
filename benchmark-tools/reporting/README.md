# Benchmark publication tools

This directory contains deterministic builders for the repository's uniform
benchmark reports. Published CSV and JSON are the source of truth; plots and
Markdown summarize those same rows.

Install the plotting dependencies with
`python -m pip install -r benchmark-tools/reporting/requirements.txt`.

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
