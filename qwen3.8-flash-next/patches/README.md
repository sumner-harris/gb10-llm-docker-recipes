# Qwen3.8-Flash-Next runtime overlays

These Apache-2.0 files are the exact read-only overlays mounted by the
validated single-GB10 Qwen service. They are locked to vLLM commit
`8a728663c1c3eeace834a95f5654fa653cc1998c`; do not use them with another
image without rebasing and revalidating every file.

The files were captured from the live deployment and verified against
`SHA256SUMS`. The underlying work is based on vLLM and retains vLLM's SPDX and
copyright headers.

| Files | Purpose | Provenance |
| --- | --- | --- |
| `ple_layer.py`, `ple_mmap.py`, `model_state.py` | Keep the 47.68-GiB PLE table on local NVMe and stage only required rows | Single-Spark implementation from `tonyd2wild/Qwen3.8-Flash-Next-NVFP4-DGX-Spark`, source tree commit `6ad1c8f15cbab1ababd2048e8e5f94094dbfc4a0` plus its deployed working tree |
| `mtp_draft_vocab.py` | Reduced 65,536-token draft vocabulary; target verification still uses the full vocabulary | Same source tree and deployed working tree |
| `qsa_cache.py` | QSA paged side-cache implementation used by the qualified MTP 1–10 sweep and selected MTP=2 service | Exact live overlay, based on vLLM's Apache-2.0 QSA cache implementation |
| `upstream-overlays/ops_ple.py` | Concurrent-prefill PLE state-index correction | vLLM PR #55375, peakcrosser7 |
| `upstream-overlays/ops_qsa.py`, `qsa.py`, `platforms_interface.py` | FP8/NVFP4 KV support on the QSA path | vLLM PR #54846, andreasgru |
| `upstream-overlays/modelopt.py` | ModelOpt MTP layer-index and block-FP8 MoE loading corrections | Deployed source-tree version; the same gaps were independently addressed by sfxnz and MiaAI-Lab |

The recipe uses bind mounts rather than modifying or redistributing the pinned
container image. `launch.sh` verifies every overlay hash before Docker starts.
