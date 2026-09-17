# GB10 LLM Docker recipes

Known-good, reproducible Docker launch recipes for open-weight LLMs on NVIDIA
GB10 systems such as DGX Spark and HP ZGX Nano.

Each recipe pins both the serving image and model checkpoint. Secrets are never
stored in the repository; gated models read `HF_TOKEN` from the environment.

## Recipes

| Model | Runtime | API port | Notes |
| --- | --- | ---: | --- |
| [Mistral Small 4 119B NVFP4](mistral-small-4-119b-nvfp4/) | vLLM 0.28.0 | 8021 | Validated without speculative decoding/EAGLE |
| [Nemotron-3 Super 120B NVFP4](nemotron-3-super-120b-nvfp4/) | vLLM 0.28.0 | 8031 | MTPv2 with 3 speculative tokens |
