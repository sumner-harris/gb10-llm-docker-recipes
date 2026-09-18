# GB10 LLM Docker recipes

Known-good, reproducible Docker launch recipes for open-weight LLMs on NVIDIA
GB10 systems such as DGX Spark and HP ZGX Nano.

Each recipe pins both the serving image and model checkpoint. Secrets are never
stored in the repository; gated models read `HF_TOKEN` from the environment.

## Benchmark tools

- [OpenAI-compatible capability and throughput suite](benchmark-tools/openai-compatible-suite/)
  runs AIME 2025, IFEval, and calibrated fixed-token performance workloads
  against an already-running vLLM server.
- [Uniform benchmark reporting tools](benchmark-tools/reporting/) build the
  standard speculative-decoding reports and the capability comparison chart.

## Speculative-decoding results

All reports use the same CSV/JSON metric names and the same five plots. A
parameter sweep is kept distinct from an on/off comparison.

| Model | Experiment | Result | Report |
| --- | --- | --- | --- |
| Qwen3.8-Flash-Next | MTP depth 1–10 | MTP 2 selected; 49.26 mean output tok/s; no MTP-off baseline | [Report](qwen3.8-flash-next/benchmarks/2026-09-12-mtp-sweep/) |
| Nemotron-3 Super 120B NVFP4 | Baseline vs built-in MTP3 vs external MTPv2 | External MTPv2 averaged 27.8% above baseline | [Report](nemotron-3-super-120b-nvfp4/benchmarks/2026-09-17-mtp-comparison/) |
| Mistral Small 4 119B NVFP4 | Baseline vs EAGLE-1/EAGLE-3 | Non-speculative baseline won every tested load | [Report](mistral-small-4-119b-nvfp4/benchmarks/2026-09-17-eagle-comparison/) |

## Capability results

The [capability result contract](benchmark-results/capability/) is ready for
the explicit reasoning-mode campaign now running. The main-page grouped
vertical bar chart will be published at
`benchmark-results/capability/capability-comparison.png` once a comparable,
audited matrix has completed. Provisional, capped, and reference-only runs are
excluded from that chart.

<!-- CAPABILITY_CHART: replace this note with the generated image after the
first complete comparable matrix passes the publication checks in AGENTS.md. -->

## Recipes

| Model | Runtime | API port | Notes |
| --- | --- | ---: | --- |
| [Qwen3.8-Flash-Next](qwen3.8-flash-next/) | vLLM 0.28.1 development build | 8000 | MTP sweep selected 2 draft tokens |
| [Mistral Small 4 119B NVFP4](mistral-small-4-119b-nvfp4/) | vLLM 0.28.0 | 8021 | Validated without speculative decoding/EAGLE |
| [Nemotron-3 Super 120B NVFP4](nemotron-3-super-120b-nvfp4/) | vLLM 0.28.0 | 8031 | MTPv2 with 3 speculative tokens |
