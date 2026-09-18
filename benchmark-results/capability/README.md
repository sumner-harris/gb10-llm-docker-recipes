# Capability comparison data

This directory is the repository-wide index for audited capability results.
The main-page vertical bar chart will be generated here as
`capability-comparison.png` after the first complete comparable matrix is
published.

One CSV row represents one metric for one model and one explicit reasoning
mode. Scores are stored on a 0–1 scale. Only `result_status=PASS` rows may be
drawn. Every row links to a dated model-local report containing raw-sample
provenance, exact outbound reasoning controls, prompt/task versions, generation
settings, cap/timeout audits, and that model's detailed plots.

Canonical chart metrics are:

- `aime25_accuracy`
- `gpqa_diamond_accuracy`
- `ifeval_prompt_strict`
- `ifeval_instruction_strict`

Model-local reports live at
`<model>/benchmarks/YYYY-MM-DD-capability-<mode>/`. A report must remain
`reference-only` or `provisional` until all requested samples have valid,
non-truncated responses and the exact reasoning mode is proven in captured
outbound payloads.
