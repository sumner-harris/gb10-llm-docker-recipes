#!/usr/bin/env python3
"""Normalize the retained Mistral and Nemotron comparison publications."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTS = {
    "mistral-small-4-119b-nvfp4/benchmarks/2026-09-17-eagle-comparison": {
        "model": {
            "served_id": "mistral-small-4-119b-nvfp4",
            "display_name": "Mistral Small 4 119B NVFP4",
            "checkpoint": "mistralai/Mistral-Small-4-119B-2603-NVFP4",
            "revision": "45331841b631f4e281df8e959ea3cc9beb84298a",
        },
        "runtime": {
            "name": "vLLM", "version": "0.28.0",
            "container_image": "vllm/vllm-openai@sha256:61fc8a896b0a4fbbbdc063bc4b0dbc25ce98e02b5050c24aeb7830ac02039b14",
        },
        "workload": {
            "dataset": "nvidia/SPEED-Bench", "config": "throughput_2k",
            "prompts_per_cell": 10, "max_output_tokens": 512,
            "concurrencies": [1, 2, 4, 6], "reasoning_modes": ["none", "high"],
            "measured_repeats": 3, "warmup_batches_excluded": 2,
        },
        "variants": [
            {"id": "baseline", "label": "Baseline (no speculation)", "draft_tokens": 0},
            {"id": "eagle1", "label": "Official EAGLE, 1 draft token", "draft_tokens": 1, "draft_checkpoint": "mistralai/Mistral-Small-4-119B-2603-eagle"},
            {"id": "eagle3", "label": "Official EAGLE, 3 draft tokens", "draft_tokens": 3, "draft_checkpoint": "mistralai/Mistral-Small-4-119B-2603-eagle"},
        ],
        "result": {"winner": "baseline", "mean_system_output_tok_s": {"baseline": 54.58518970477416, "eagle1": 31.07070071400919, "eagle3": 29.192493924420706}},
        "limitations": [
            "The EAGLE compatibility image was a local derived image rather than a registry-pinned artifact.",
            "High reasoning frequently consumed the 512-token performance cap; visible-answer rate is reported separately and no capability claim is made.",
            "One EAGLE-3 timeout cell was quarantined and rerun completely after a clean restart; only the successful replacement cell is published.",
            "This historical throughput report predates per-request outbound-payload capture and is excluded from capability-score comparisons.",
        ],
    },
    "nemotron-3-super-120b-nvfp4/benchmarks/2026-09-17-mtp-comparison": {
        "model": {
            "served_id": "nemotron-3-super-120b-nvfp4",
            "display_name": "Nemotron-3 Super 120B NVFP4",
            "checkpoint": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4",
            "revision": "ff433f5493e25d631c9f12b5d55c674229923d02",
        },
        "runtime": {
            "name": "vLLM", "version": "0.28.0",
            "container_image": "vllm/vllm-openai@sha256:f8fe15a8039343336945db10494eaad80ef941fe2b2a5fa6649fa38636051a65",
        },
        "workload": {
            "dataset": "nvidia/SPEED-Bench", "config": "throughput_2k",
            "prompts_per_cell": 10, "max_output_tokens": 512,
            "concurrencies": [1, 2, 4, 6],
            "historical_reasoning_labels": ["none", "low", "medium", "xhigh"],
            "measured_repeats": 1, "warmup_batches_excluded": 2,
        },
        "variants": [
            {"id": "baseline", "label": "Baseline (no speculation)", "draft_tokens": 0},
            {"id": "builtin_mtp3", "label": "Built-in MTP, 3 draft tokens", "draft_tokens": 3},
            {"id": "mtpv2_mtp3", "label": "External MTPv2, 3 draft tokens", "draft_tokens": 3, "draft_checkpoint": "nvidia/Nemotron-3-Super-120B-A12B-BF16-MTPv2", "draft_revision": "c929f8a55d0527fea9f58b4cedc9e0c855cfc421"},
        ],
        "result": {"winner": "mtpv2_mtp3", "mean_system_output_tok_s": {"baseline": 23.992523778424758, "builtin_mtp3": 28.215812528551293, "mtpv2_mtp3": 30.02549403378194}},
        "limitations": [
            "Each effort/concurrency/deployment cell has one measured repeat.",
            "The external MTPv2 deployment required GPU-memory utilization 0.82 instead of 0.80 to retain the full context window.",
            "The historical none/low/medium/xhigh labels predate the current model-native reasoning-mode mapping and exact outbound-payload capture; the reasoning-mode facet is reference-only and excluded from capability-score comparisons.",
            "The 512-token workload measures serving performance, not capability accuracy.",
        ],
    },
}


INT_FIELDS = {"draft_tokens", "concurrency", "repeats", "successful_requests", "repeat", "success_count", "request_count", "ttfo_count"}


def typed(row: dict[str, str]) -> dict[str, object]:
    converted: dict[str, object] = {}
    for key, value in row.items():
        if value == "":
            converted[key] = None
        elif key in INT_FIELDS:
            converted[key] = int(value)
        elif key in {"variant", "label", "effort", "source_file"}:
            converted[key] = value
        else:
            try:
                converted[key] = float(value)
            except ValueError:
                converted[key] = value
    return converted


def normalize_source(row: dict[str, str]) -> None:
    filename = row["source_file"].replace("\\", "/").rsplit("/", 1)[-1]
    row["source_file"] = f"{row['variant']}/cells/{filename}"


def main() -> None:
    for relative, metadata in REPORTS.items():
        report_dir = ROOT / relative
        by_repeat_path = report_dir / "comparison_by_repeat.csv"
        with by_repeat_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            by_repeat = list(reader)
        assert fields
        for row in by_repeat:
            normalize_source(row)
        with by_repeat_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(by_repeat)

        with (report_dir / "comparison_summary.csv").open(encoding="utf-8", newline="") as handle:
            summary = list(csv.DictReader(handle))
        document = {
            "schema_version": "1.0.0",
            "benchmark_type": "speculative_comparison",
            "status": "complete",
            "model": metadata["model"],
            "hardware": "NVIDIA GB10",
            "runtime": metadata["runtime"],
            "workload": metadata["workload"],
            "variants": metadata["variants"],
            "result": metadata["result"],
            "selection_rule": {
                "description": "Highest measured system output throughput while preserving the declared workload contract",
                "selected_variant": metadata["result"]["winner"],
            },
            "limitations": metadata["limitations"],
            "summary_rows": [typed(row) for row in summary],
            "per_repeat_rows": [typed(row) for row in by_repeat],
        }
        (report_dir / "comparison_report.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        print(relative, len(summary), len(by_repeat))


if __name__ == "__main__":
    main()
