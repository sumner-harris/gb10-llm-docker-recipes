# Qwen3.8-Flash-Next

Benchmark publications for the OpenAI-compatible vLLM deployment of
Qwen3.8-Flash-Next.

## Benchmarks

- [MTP 1–10 parameter sweep (2026-09-12)](benchmarks/2026-09-12-mtp-sweep/)

The MTP sweep selected two draft tokens per step for this single-GB10 setup.
It did not include an MTP-off deployment, so it is a tuning result rather than
a claim about speculative-decoding uplift.
