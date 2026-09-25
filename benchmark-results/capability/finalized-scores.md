# Finalized capability scores

Snapshot: 2026-09-25. All values are percentages. Only explicit, temperature-zero runs that completed their task-level audit are included. A dagger (†) means one or more capped/null outputs were retained as the run's single response and scored incorrect. A dash means that task/mode is not yet finalized and is not present in `scores.csv`.

| Model | Explicit mode | AIME 2025 | IFEval prompt strict | IFEval prompt loose | IFEval instruction strict | IFEval instruction loose | GPQA Diamond |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.8 Flash Next | OFF | 76.67 | — | — | — | — | — |
| Mistral Small 4 | NONE | 33.33 | 75.79 | 79.67 | 83.09 | 86.33 | 58.59 |
| Mistral Small 4 | HIGH | 80.00 | 83.92 | 87.06 | 89.33 | 91.49 | 76.26 |
| Gemma 4 31B | OFF | 60.00 | 91.50 | 92.79 | 94.12 | 95.20 | 74.24† |
| Gemma 4 31B | HIGH | 86.67 | 92.24† | 93.72† | 93.65† | 94.72† | 81.82† |
| Nemotron 3 Super | OFF | 76.67† | 80.22† | 84.66† | 86.57† | 89.69† | 77.27 |
| Nemotron 3 Super | LOW | 46.67 | 86.69† | 90.02† | 90.77† | 93.41† | 59.60 |
| Nemotron 3 Super | REGULAR | 93.33 | 89.83† | 91.87† | 92.81† | 94.24† | 72.73† |
| GPT-OSS 120B | LOW | 46.67 | — | — | — | — | — |

GPQA uses the corrected AA-compatible robust extractor. AIME uses robust final-integer extraction. IFEval values are the official prompt/instruction strict/loose metrics. Missing final answers are ordinary incorrect answers and do not receive a dagger. Qualified nonfinal, reference-only, vendor-extra, partial, and active runs are excluded.

## Published graphs

- `capability-comparison.png`: canonical four-metric overview.
- `aime25-comparison.png`: finalized AIME 2025 scores.
- `gpqa-diamond-comparison.png`: finalized robust GPQA Diamond scores.
- `ifeval-comparison.png`: all four finalized IFEval metrics.
