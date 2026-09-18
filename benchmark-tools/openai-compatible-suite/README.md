# OpenAI-compatible capability and throughput suite

This client-only harness compares already-running vLLM servers with one
deterministic capability pass and a separate fixed-work throughput matrix. It
does not start, stop, or reconfigure a model server.

## What it runs

Capability scoring is sequential by task and is **not** a concurrency sweep:

- AIME 2025, with the lm-eval metric plus a transparent final-integer rescore.
- IFEval, using the task's strict and loose instruction-following metrics.
- GPQA Diamond through the official lm-eval task
  `gpqa_diamond_cot_zeroshot` (deterministic `generate_until`/chain-of-thought)
  and the gated `Idavidrein/gpqa` dataset.
- One deterministic pass (`temperature=0`) with a 130,000-token generation
  ceiling and a 21,600-second (six-hour) per-request timeout.
- Raw lm-eval samples and a strict post-run token-count audit that rejects
  empty responses and likely generation-limit hits until they are recovered.

`EVAL_CONCURRENCY=4` lets lm-eval submit four independent examples at once to
reduce wall time. It does not duplicate samples, change the task, or produce
scores at several concurrency levels. Set it to `1` if the server cannot batch
requests reliably; use the same value for every model in a comparison.

The long capability timeout is intentional: reasoning models can produce valid
130K-budget generations that take several hours. A shorter client timeout
would cancel and effectively truncate those samples even though the server is
still generating. `EVAL_TIMEOUT` remains configurable, but comparisons should
use the same value and report any client timeout. Performance requests use the
separate `PERF_TIMEOUT=3600`, so changing capability tolerance does not change
the fixed-output workload.

GPQA is an access-gated first-class stage. With the default `RUN_GPQA=auto`,
the runner checks for a cached Hugging Face login or `HF_TOKEN` and verifies
that `datasets` can load the official `gpqa_diamond` builder and its gated data
artifacts. A metadata-only repository lookup is not accepted as proof of data
access. When authentication or dataset entitlement is missing, it writes
`gpqa_access.json`, records `BLOCKED` in
`lm_eval_status.txt`, and continues AIME, IFEval, and performance testing. It
never downloads or substitutes unofficial GPQA data. To enable the stage:

1. Sign in at <https://huggingface.co/datasets/Idavidrein/gpqa> and accept or
   request the dataset license.
2. Run `hf auth login` on the benchmark client, or export `HF_TOKEN` only in
   the benchmark process environment. Never commit the token.
3. Keep `GPQA_TASK=gpqa_diamond_cot_zeroshot` for every compared model. The
   pinned lm-eval commit in `requirements.txt` is part of the benchmark version.

The performance stage forces exact output lengths with vLLM's `ignore_eos`
extension and runs 24 requests for every cell:

| Scenario | Rendered chat input | Forced output | Concurrency |
| --- | ---: | ---: | --- |
| `interactive` | 512 tokens | 256 tokens | 1, 4, 8 |
| `long_context` | 8,192 tokens | 1,024 tokens | 1, 4, 8 |
| `long_generation` | 32,768 tokens | 4,096 tokens | 1, 4, 8 |

Input lengths are calibrated through vLLM's `/tokenize` endpoint and must
match exactly. The runner records request throughput, system output tokens/s,
TTFT p50/p95, end-to-end p50/p95/mean, usage, finish reasons, and failures.
Each cell is written atomically before the next begins, so rerunning with the
same `RUN_DIR` resumes completed cells.

## Install and configure

Requirements: Linux, Bash, Python 3.10 or newer, and network access to a vLLM
server exposing `/v1/models`, `/v1/chat/completions`, and `/tokenize`.

```bash
cd benchmark-tools/openai-compatible-suite
bash install.sh
cp config.env.example config.env
```

Edit `config.env`. `BASE_URL` is the server origin before `/v1`. Leave
`MODEL_ID` empty only when the endpoint advertises exactly one model. Keep API
keys outside version control; `config.env` and `results/` are ignored.

Before comparing models, hold constant the checkpoint revision, chat template,
reasoning mode, quantization, vLLM version and flags, KV-cache dtype,
speculative decoding, context limit, and hardware power/clock policy. A
130,000-token client ceiling cannot override a smaller server context window.
The default assumes at least a 131,072-token server context and rendered prompts
of at most 1,072 tokens; verify prompt plus output fits before comparing models.

## Run or resume

Start a new timestamped run:

```bash
bash run_all.sh
```

Resume an interrupted performance matrix in an existing result directory:

```bash
set -a
source config.env
set +a
RUN_DIR=results/20260917T183139Z .venv/bin/python scripts/run_perf.py
```

Run the stages separately when desired:

```bash
export RUN_DIR=results/manual
.venv/bin/python scripts/probe_endpoint.py
bash scripts/run_lm_eval.sh
bash scripts/run_gpqa.sh
bash scripts/postprocess_capability.sh
.venv/bin/python scripts/run_perf.py
```

Do not run AIME, IFEval, GPQA, the capability audit, or another load generator
while measuring throughput on the same endpoint. One benchmark client can run
against each independent server in parallel, but two clients must not share a
server under test. Use the same official GPQA task and pinned harness version
across every model; results from different task configurations are not a fair
comparison.

## Results and interpretation

The important outputs are:

```text
results/<run>/
  probe.json
  lm_eval_status.txt
  gpqa_access.json                 # ACCESSIBLE or safe BLOCKED/ERROR details
  lm_eval/                         # official results and raw samples
  aime_rescore.json                # transparent robust extraction
  capability_output_audit.json     # suspected generation-cap hits
  performance.json                 # one summary per completed cell
  performance_requests.jsonl       # request-level timing/usage/errors
  performance/
    run_config.json
    cells/<scenario>_c<N>.json      # atomic resume checkpoints
```

Treat empty or length-limited capability answers as incomplete. The suite exits
nonzero when the audit finds either condition; recover those prompts at a safe
ceiling before treating the aggregate score as final. Some reasoning endpoints
return a null `message.content` with text only in a provider-specific reasoning
field, so inspect the raw API response rather than scoring an empty placeholder.
The AIME rescore accommodates common `Answer: N` and `\\boxed{N}` endings; use
this same scorer for every compared model and retain lm-eval's stock metric for
provenance. Fixed-output performance cells should have 24 successes, 24 exact
output counts, and finish reason `length`. Any other result is a failed or
qualified cell, not a directly comparable measurement.

Output tokens/s is tokenizer-dependent. For cross-family comparisons, report
latency and task accuracy alongside token throughput, and consider
correct-answers-per-GPU-hour rather than treating unlike tokenizers as equal
units of useful work.

Run the control-flow regression tests with:

```bash
python -m unittest discover -s tests -v
```
