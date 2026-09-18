#!/usr/bin/env python3
"""Build the sanitized, uniform Qwen MTP sweep publication from retained cells."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


EFFORTS = ("none", "low", "medium", "xhigh")
CONCURRENCIES = (1, 2, 4, 6)
CELL_RE = re.compile(r"mtp(?P<mtp>\d+)_(?P<effort>none|low|medium|xhigh)_c(?P<c>\d+)\.json")
BY_REPEAT_FIELDS = (
    "effort", "variant", "label", "draft_tokens", "concurrency", "repeat",
    "successful_requests", "error_count", "system_output_tok_s", "ttft_p50_s",
    "ttft_p90_s", "ttft_mean_s", "ttfo_p50_s", "visible_answer_rate",
    "reasoning_share", "draft_acceptance_rate", "mean_acceptance_length",
    "completion_tokens_per_joule", "source_file", "source_sha256",
)
SUMMARY_FIELDS = (
    "variant", "label", "draft_tokens", "scenario_count", "successful_requests",
    "mean_system_output_tok_s", "mean_completion_tokens_per_joule",
    "mean_ttft_p90_s", "mean_draft_acceptance_rate", "weighted_draft_acceptance_rate",
    "weighted_mean_acceptance_length", "throughput_ratio", "efficiency_ratio",
    "inverse_ttft_ratio", "balanced_score", "rank",
)


def q(value: object) -> str:
    return "" if value is None else str(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(source: Path) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    raw: list[dict] = []
    for path in sorted((source / "cells").glob("mtp*.json")):
        match = CELL_RE.fullmatch(path.name)
        if not match:
            continue
        mtp = int(match.group("mtp"))
        effort = match.group("effort")
        concurrency = int(match.group("c"))
        data = json.loads(path.read_text(encoding="utf-8"))
        summary = data["summary"]
        requests = data.get("requests", [])
        visible = sum(1 for request in requests if request.get("ttfo_s") is not None)
        rows.append({
            "effort": effort,
            "variant": f"mtp{mtp}",
            "label": f"MTP {mtp}",
            "draft_tokens": mtp,
            "concurrency": concurrency,
            "repeat": 1,
            "successful_requests": summary["success_count"],
            "error_count": summary["error_count"],
            "system_output_tok_s": summary["system_output_tok_s"],
            "ttft_p50_s": summary["ttft_s"]["p50"],
            "ttft_p90_s": summary["ttft_s"]["p90"],
            "ttft_mean_s": summary["ttft_s"]["mean"],
            "ttfo_p50_s": summary["ttfo_s"]["p50"] if summary["ttfo_s"] else None,
            "visible_answer_rate": visible / summary["success_count"],
            "reasoning_share": summary["reasoning_share"],
            "draft_acceptance_rate": summary["draft_acceptance_rate"],
            "mean_acceptance_length": summary["mean_acceptance_length"],
            "completion_tokens_per_joule": summary["completion_tokens_per_joule"],
            "source_file": f"retained-source/cells/{path.name}",
            "source_sha256": sha256(path),
        })
        raw.append({"mtp": mtp, "effort": effort, "concurrency": concurrency, "summary": summary})
    expected = {(mtp, effort, concurrency) for mtp in range(1, 11) for effort in EFFORTS for concurrency in CONCURRENCIES}
    actual = {(row["draft_tokens"], row["effort"], row["concurrency"]) for row in rows}
    if actual != expected:
        raise ValueError(f"cell matrix mismatch: missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    if any(row["successful_requests"] != 10 or row["error_count"] != 0 for row in rows):
        raise ValueError("every publishable cell must have 10 successes and zero errors")
    return rows, raw


def summarize(rows: list[dict], raw: list[dict]) -> list[dict]:
    by_scenario: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        by_scenario[(row["effort"], row["concurrency"])].append(row)
    ratios: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for scenario_rows in by_scenario.values():
        best_throughput = max(row["system_output_tok_s"] for row in scenario_rows)
        best_efficiency = max(row["completion_tokens_per_joule"] for row in scenario_rows)
        best_ttft = min(row["ttft_p90_s"] for row in scenario_rows)
        for row in scenario_rows:
            mtp = row["draft_tokens"]
            ratios[mtp]["throughput"].append(row["system_output_tok_s"] / best_throughput)
            ratios[mtp]["efficiency"].append(row["completion_tokens_per_joule"] / best_efficiency)
            ratios[mtp]["ttft"].append(best_ttft / row["ttft_p90_s"])
    output: list[dict] = []
    for mtp in range(1, 11):
        selected = [row for row in rows if row["draft_tokens"] == mtp]
        raw_selected = [row["summary"] for row in raw if row["mtp"] == mtp]
        drafts = sum(float(item["draft_tokens"]) for item in raw_selected)
        accepted = sum(float(item["accepted_draft_tokens"]) for item in raw_selected)
        steps = sum(float(item["draft_steps"]) for item in raw_selected)
        throughput_ratio = sum(ratios[mtp]["throughput"]) / 16
        efficiency_ratio = sum(ratios[mtp]["efficiency"]) / 16
        inverse_ttft_ratio = sum(ratios[mtp]["ttft"]) / 16
        output.append({
            "variant": f"mtp{mtp}", "label": f"MTP {mtp}", "draft_tokens": mtp,
            "scenario_count": 16,
            "successful_requests": sum(row["successful_requests"] for row in selected),
            "mean_system_output_tok_s": sum(row["system_output_tok_s"] for row in selected) / 16,
            "mean_completion_tokens_per_joule": sum(row["completion_tokens_per_joule"] for row in selected) / 16,
            "mean_ttft_p90_s": sum(row["ttft_p90_s"] for row in selected) / 16,
            "mean_draft_acceptance_rate": sum(row["draft_acceptance_rate"] for row in selected) / 16,
            "weighted_draft_acceptance_rate": accepted / drafts,
            "weighted_mean_acceptance_length": 1 + accepted / steps,
            "throughput_ratio": throughput_ratio,
            "efficiency_ratio": efficiency_ratio,
            "inverse_ttft_ratio": inverse_ttft_ratio,
            "balanced_score": 0.5 * throughput_ratio + 0.3 * efficiency_ratio + 0.2 * inverse_ttft_ratio,
        })
    ranked = sorted(output, key=lambda row: row["balanced_score"], reverse=True)
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    return output


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def plot(
    rows: list[dict], output: Path, field: str, ylabel: str, filename: str,
    ylim: tuple[float, float] | None = None,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    colors = {1: "#4C78A8", 2: "#F58518", 4: "#54A24B", 6: "#E45756"}
    for axis, effort in zip(axes.flat, EFFORTS):
        for concurrency in CONCURRENCIES:
            selected = sorted(
                (row for row in rows if row["effort"] == effort and row["concurrency"] == concurrency),
                key=lambda row: row["draft_tokens"],
            )
            y = [row[field] if row[field] is not None else math.nan for row in selected]
            axis.plot(range(1, 11), y, marker="o", linewidth=1.8, color=colors[concurrency], label=f"c={concurrency}")
        axis.set_title("OFF / non-thinking" if effort == "none" else effort)
        axis.grid(alpha=0.25)
        axis.set_xticks(range(1, 11))
        if ylim:
            axis.set_ylim(*ylim)
    axes[0, 0].legend(ncol=2, frameon=False)
    fig.supxlabel("MTP draft tokens per step")
    fig.supylabel(ylabel)
    fig.suptitle("Qwen3.8-Flash-Next MTP 1–10 sweep", fontweight="bold")
    fig.tight_layout(rect=(0.03, 0.03, 1, 0.96))
    fig.savefig(output / filename, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Retained mtp1_10_speedbench result directory")
    parser.add_argument("output", type=Path, help="Dated report directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, raw = load_rows(args.source)
    summary = summarize(rows, raw)
    write_csv(args.output / "comparison_by_repeat.csv", BY_REPEAT_FIELDS, rows)
    write_csv(args.output / "comparison_summary.csv", SUMMARY_FIELDS, summary)
    report = {
        "schema_version": "1.0.0",
        "benchmark_type": "speculative_parameter_sweep",
        "status": "complete",
        "model": {"served_id": "qwen3.8-flash-next", "display_name": "Qwen3.8-Flash-Next"},
        "hardware": "NVIDIA GB10",
        "runtime": {"name": "vLLM", "version": "0.28.1rc1.dev388+g8a728663c", "container_image": "vllm/vllm-openai:nightly-8a728663c1c3eeace834a95f5654fa653cc1998c"},
        "workload": {"dataset": "nvidia/SPEED-Bench", "config": "throughput_2k", "prompts_per_cell": 10, "max_output_tokens": 512, "concurrencies": list(CONCURRENCIES), "reasoning_modes": list(EFFORTS), "warmup_batches_excluded": 2, "prefix_caching": False, "sampling": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}},
        "selection_rule": {"description": "Mean of per-scenario ratios", "balanced_score": "0.5*throughput_ratio + 0.3*efficiency_ratio + 0.2*inverse_ttft_ratio", "selected_variant": "mtp2"},
        "limitations": ["No MTP-off baseline was measured; this report selects a draft-token depth and does not estimate uplift versus no speculation.", "Each matrix cell has one measured repeat.", "The historical 'none' effort is displayed as OFF/non-thinking; exact wire semantics were not recorded as a full outbound payload in this older run.", "The historical capture retained the image build tag and vLLM git-based version, but not the registry digest or model checkpoint revision."],
        "summary_rows": summary,
        "per_repeat_rows": rows,
    }
    (args.output / "comparison_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    plot(rows, args.output, "system_output_tok_s", "System output tokens/s", "throughput_comparison.png")
    plot(rows, args.output, "ttft_p50_s", "TTFT p50 (s)", "ttft_comparison.png")
    plot(rows, args.output, "ttfo_p50_s", "First-answer latency p50 (s)", "first_answer_latency_comparison.png")
    plot(rows, args.output, "draft_acceptance_rate", "Draft-token acceptance", "acceptance_comparison.png", (0, 1))
    plot(rows, args.output, "reasoning_share", "Reasoning-token share", "reasoning_share_comparison.png", (0, 1))
    print(json.dumps({"cells": len(rows), "requests": sum(row["successful_requests"] for row in rows), "selected": min(summary, key=lambda row: row["rank"])["variant"]}))


if __name__ == "__main__":
    main()
