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
parameter sweep is kept distinct from an on/off comparison. Cross-model token
rates describe these particular single-GB10 deployments; algorithm uplift is
only shown where the same-model report includes a no-speculation baseline.

| Model | Type | Selected configuration | Mean output tok/s | vs baseline | Draft acceptance | Key qualification | Report |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| Qwen3.8-Flash-Next | MTP depth sweep | MTP 2 | 49.26 | n/a | 56.2% | No MTP-off baseline; one repeat per cell | [Report](qwen3.8-flash-next/benchmarks/2026-09-12-mtp-sweep/) |
| Nemotron-3 Super 120B NVFP4 | Speculative comparison | External MTPv2, 3 tokens | 30.03 | +27.8% | 60.8% | One repeat; historical reasoning labels | [Report](nemotron-3-super-120b-nvfp4/benchmarks/2026-09-17-mtp-comparison/) |
| Mistral Small 4 119B NVFP4 | Speculative comparison | Baseline (no speculation) | 54.59 | +0.0% | n/a | Three repeats; EAGLE slower in every cell | [Report](mistral-small-4-119b-nvfp4/benchmarks/2026-09-17-eagle-comparison/) |

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
