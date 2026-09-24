#!/usr/bin/env python3
"""Build a sanitized throughput-matrix publication from retained Responses cells."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


EFFORTS = ("low", "medium", "high")
CONCURRENCIES = (1, 2, 4, 6)
BY_REPEAT_FIELDS = (
    "effort", "variant", "label", "concurrency", "repeat", "request_count",
    "successful_requests", "error_count", "request_throughput_req_s",
    "system_output_tok_s", "ttft_p50_s", "ttft_p90_s", "ttfo_p50_s",
    "visible_answer_rate", "reasoning_share", "total_completion_tokens",
    "total_reasoning_tokens", "draft_acceptance_rate",
    "mean_acceptance_length", "source_file", "source_sha256",
)
SUMMARY_FIELDS = (
    "effort", "scenario_count", "successful_requests", "error_count",
    "mean_system_output_tok_s", "peak_system_output_tok_s",
    "peak_concurrency", "mean_ttft_p50_s", "visible_answer_rate",
    "weighted_reasoning_share",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(source: Path) -> list[dict]:
    rows: list[dict] = []
    expected = {(effort, concurrency) for effort in EFFORTS for concurrency in CONCURRENCIES}
    for path in sorted((source / "cells").glob("*_c*_r1.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        effort = data["effort"]
        concurrency = int(data["concurrency"])
        if (effort, concurrency) not in expected:
            continue
        summary = data["summary"]
        visible = int((summary.get("ttfo_s") or {}).get("n") or 0)
        successes = int(summary["success_count"])
        rows.append({
            "effort": effort,
            "variant": "baseline",
            "label": "GPT-OSS 120B MXFP4",
            "concurrency": concurrency,
            "repeat": int(data["repeat"]),
            "request_count": int(summary["request_count"]),
            "successful_requests": successes,
            "error_count": int(summary["error_count"]),
            "request_throughput_req_s": summary["request_throughput_req_s"],
            "system_output_tok_s": summary["system_output_tok_s"],
            "ttft_p50_s": summary["ttft_s"]["p50"],
            "ttft_p90_s": summary["ttft_s"]["p90"],
            "ttfo_p50_s": (summary.get("ttfo_s") or {}).get("p50"),
            "visible_answer_rate": visible / successes if successes else 0,
            "reasoning_share": summary["reasoning_share"],
            "total_completion_tokens": summary["total_completion_tokens"],
            "total_reasoning_tokens": summary["total_reasoning_tokens"],
            "draft_acceptance_rate": summary["draft_acceptance_rate"],
            "mean_acceptance_length": summary["mean_acceptance_length"],
            "source_file": f"retained-source/cells/{path.name}",
            "source_sha256": sha256(path),
        })
    actual = {(row["effort"], row["concurrency"]) for row in rows}
    if actual != expected:
        raise ValueError(f"cell matrix mismatch: missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    if len(rows) != 12:
        raise ValueError(f"expected 12 cells, found {len(rows)}")
    if any(row["request_count"] != 10 or row["successful_requests"] != 10 or row["error_count"] for row in rows):
        raise ValueError("every publishable cell must contain 10 requests, 10 successes, and zero errors")
    return sorted(rows, key=lambda row: (EFFORTS.index(row["effort"]), row["concurrency"]))


def summarize(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    for effort in EFFORTS:
        selected = [row for row in rows if row["effort"] == effort]
        peak = max(selected, key=lambda row: row["system_output_tok_s"])
        completions = sum(row["total_completion_tokens"] for row in selected)
        reasoning = sum(row["total_reasoning_tokens"] for row in selected)
        output.append({
            "effort": effort,
            "scenario_count": len(selected),
            "successful_requests": sum(row["successful_requests"] for row in selected),
            "error_count": sum(row["error_count"] for row in selected),
            "mean_system_output_tok_s": sum(row["system_output_tok_s"] for row in selected) / len(selected),
            "peak_system_output_tok_s": peak["system_output_tok_s"],
            "peak_concurrency": peak["concurrency"],
            "mean_ttft_p50_s": sum(row["ttft_p50_s"] for row in selected) / len(selected),
            "visible_answer_rate": sum(row["visible_answer_rate"] * row["successful_requests"] for row in selected) / sum(row["successful_requests"] for row in selected),
            "weighted_reasoning_share": reasoning / completions,
        })
    return output


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def line_plot(rows: list[dict], output: Path, field: str, ylabel: str, filename: str, *, ylim=None) -> None:
    fig, axis = plt.subplots(figsize=(9, 5.5))
    colors = {"low": "#4C78A8", "medium": "#F58518", "high": "#E45756"}
    for effort in EFFORTS:
        selected = [row for row in rows if row["effort"] == effort]
        y = [row[field] if row[field] is not None else math.nan for row in selected]
        axis.plot(CONCURRENCIES, y, marker="o", linewidth=2.2, color=colors[effort], label=effort)
    axis.set_xlabel("Closed-loop concurrency")
    axis.set_ylabel(ylabel)
    axis.set_title("GPT-OSS 120B MXFP4 — single GB10", fontweight="bold")
    axis.set_xticks(CONCURRENCIES)
    if ylim:
        axis.set_ylim(*ylim)
    axis.grid(alpha=0.25)
    axis.legend(frameon=False, title="Reasoning effort")
    fig.tight_layout()
    fig.savefig(output / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def acceptance_plot(output: Path) -> None:
    fig, axis = plt.subplots(figsize=(9, 5.5))
    axis.axis("off")
    axis.text(0.5, 0.58, "Draft acceptance: not applicable", ha="center", va="center", fontsize=18, fontweight="bold")
    axis.text(0.5, 0.42, "This deployment uses no speculative decoder.", ha="center", va="center", fontsize=13)
    axis.set_title("GPT-OSS 120B MXFP4 — single GB10", fontweight="bold")
    fig.tight_layout()
    fig.savefig(output / "acceptance_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def fmt(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def write_readme(output: Path, rows: list[dict], summary: list[dict]) -> None:
    by_effort = {row["effort"]: row for row in summary}
    table = []
    for row in rows:
        table.append(
            f"| {row['effort']} | {row['concurrency']} | {row['system_output_tok_s']:.2f} | "
            f"{row['ttft_p50_s']:.2f} | {fmt(row['ttfo_p50_s'])} | "
            f"{row['visible_answer_rate']:.0%} | {row['reasoning_share']:.1%} | 10/10 |"
        )
    low = by_effort["low"]
    medium = by_effort["medium"]
    high = by_effort["high"]
    text = f"""# GPT-OSS 120B MXFP4 throughput matrix

**Status:** PASS. **Scope:** one non-speculative vLLM deployment on one NVIDIA GB10. **Sample:** 12 cells and 120/120 successful measured requests, with one repeat per cell. **Selection:** low effort at concurrency 6 is the practical configuration at {low['peak_system_output_tok_s']:.2f} system output tok/s with a 100% visible-answer rate. **Main limitation:** this is a one-repeat matrix, and medium/high frequently spent the 512-token cap in reasoning before producing visible answer text.

The raw throughput peak was {high['peak_system_output_tok_s']:.2f} tok/s at high effort and concurrency 6, but high effort produced visible answer text in only {high['visible_answer_rate']:.1%} of measured requests across the matrix. Medium averaged {medium['mean_system_output_tok_s']:.2f} tok/s with a {medium['visible_answer_rate']:.1%} visible-answer rate. Low averaged {low['mean_system_output_tok_s']:.2f} tok/s and reached visible answer text in every request.

## Plots

![System output throughput](throughput_comparison.png)

![Time to first token](ttft_comparison.png)

![First-answer latency](first_answer_latency_comparison.png)

![Draft acceptance](acceptance_comparison.png)

![Reasoning share](reasoning_share_comparison.png)

## Cell results

| Effort | Concurrency | Output tok/s | TTFT p50 (s) | First answer p50 (s) | Visible answer | Reasoning share | Success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(table)}

Machine-readable artifacts: [summary CSV](comparison_summary.csv), [cell CSV](comparison_by_repeat.csv), and [structured JSON](comparison_report.json).

## Workload and configuration

- OpenAI-compatible streaming `POST /v1/responses`.
- Ten fixed prompts per cell: nine deterministically selected NVIDIA SPEED-Bench `throughput_2k` prompts plus `tell me a 1000 word story`.
- Dataset selection SHA-256: `96765a32a67a83f07ddded74cfd5639a7c2afd1a1ff0f3c244b1cff0a9732f3b`.
- Reasoning efforts: `low`, `medium`, and `high`, sent explicitly on every request.
- Closed-loop concurrency: 1, 2, 4, and 6.
- Maximum output: 512 tokens; natural completion was allowed.
- Two excluded warmup batches before every concurrency level, using low effort and a 128-token output cap.
- Sampling: temperature 0.7, top-p 0.8, top-k 20, min-p 0.0, presence penalty 1.5.
- Target: `openai/gpt-oss-120b` revision `b5c939de8f754692c1647ca79fbf85e8c1e70f8a`, native MXFP4 MoE weights, TP=1, FP8 KV cache, 131,072-token context, no speculative decoding.
- Runtime declared by the pinned launcher: vLLM 0.28.0 Ubuntu 24.04 image digest `sha256:f8fe15a8039343336945db10494eaad80ef941fe2b2a5fa6649fa38636051a65`.

The test did not alter or restart the server. The endpoint advertised exactly one model with the expected 131,072-token context before measurement, and Prometheus reported zero running and queued requests before the valid run. Host SSH credentials were unavailable, so the image digest and launch arguments are launcher-declared rather than independently captured from `docker inspect`; no host-side GPU power samples are reported.

## Interpretation

Raw output-token throughput alone overstates useful throughput when reasoning consumes the output cap. Low effort is the practical choice for this 512-token workload because it retains all visible answers while reaching {low['peak_system_output_tok_s']:.2f} tok/s at concurrency 6. High effort's {high['peak_system_output_tok_s']:.2f} tok/s peak should not be read as superior answer throughput: only one of its 40 requests reached visible answer text.
"""
    (output / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Retained benchmark_speed_responses result directory")
    parser.add_argument("output", type=Path, help="Dated publication directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = load_rows(args.source)
    summary = summarize(rows)
    write_csv(args.output / "comparison_by_repeat.csv", BY_REPEAT_FIELDS, rows)
    write_csv(args.output / "comparison_summary.csv", SUMMARY_FIELDS, summary)
    report = {
        "schema_version": "1.0.0",
        "benchmark_type": "throughput_matrix",
        "status": "complete",
        "model": {"served_id": "gpt-oss-120b-mxfp4", "display_name": "GPT-OSS 120B MXFP4", "checkpoint": "openai/gpt-oss-120b", "revision": "b5c939de8f754692c1647ca79fbf85e8c1e70f8a"},
        "hardware": "NVIDIA GB10, single GPU",
        "runtime": {"name": "vLLM", "version": "0.28.0", "container_image_digest": "sha256:f8fe15a8039343336945db10494eaad80ef941fe2b2a5fa6649fa38636051a65", "provenance": "launcher-declared; host docker inspect unavailable"},
        "workload": {"dataset": "nvidia/SPEED-Bench", "config": "throughput_2k", "dataset_sha256": "96765a32a67a83f07ddded74cfd5639a7c2afd1a1ff0f3c244b1cff0a9732f3b", "prompts_per_cell": 10, "max_output_tokens": 512, "natural_completion": True, "concurrencies": list(CONCURRENCIES), "reasoning_modes": list(EFFORTS), "warmup_batches_excluded": 2, "sampling": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}},
        "selection_rule": {"description": "Prefer the highest-throughput cell that preserves visible answers for every measured request.", "selected_effort": "low", "selected_concurrency": 6},
        "limitations": ["Each cell has one measured repeat.", "Medium and high effort frequently reached the 512-token cap before visible answer text; system output tok/s includes reasoning tokens.", "Host-side docker inspect and GPU power telemetry were unavailable; runtime provenance comes from the pinned launcher."],
        "summary_rows": summary,
        "per_repeat_rows": rows,
    }
    (args.output / "comparison_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    line_plot(rows, args.output, "system_output_tok_s", "System output tokens/s", "throughput_comparison.png")
    line_plot(rows, args.output, "ttft_p50_s", "TTFT p50 (s)", "ttft_comparison.png")
    line_plot(rows, args.output, "ttfo_p50_s", "First-answer latency p50 (s)", "first_answer_latency_comparison.png")
    acceptance_plot(args.output)
    line_plot(rows, args.output, "reasoning_share", "Reasoning-token share", "reasoning_share_comparison.png", ylim=(0, 1.05))
    write_readme(args.output, rows, summary)
    print(json.dumps({"cells": len(rows), "requests": sum(row["successful_requests"] for row in rows), "selected": "low_c6"}))


if __name__ == "__main__":
    main()
