# Capability comparison data

This directory is the repository-wide index for audited capability results.
The finalized snapshot and generated bar graphs live here. `scores.csv` is the
source of truth; `finalized-scores.md` is the compact human-readable matrix.

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
`reference-only` or `provisional` until the exact reasoning mode is proven in
captured outbound payloads and the task-level run is complete. Under the pinned
single-response policy, a completed row may use
`PASS_WITH_INVALID_OUTPUTS` when capped/null responses were retained and scored
incorrect. Such rows are final and chartable, but are visually hatched.
