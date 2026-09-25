#!/usr/bin/env python3
"""Render finalized capability comparison bar charts from the canonical CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch


FINAL_STATUSES = {"PASS", "PASS_WITH_INVALID_OUTPUTS"}
METRICS = {
    "aime25_accuracy": "AIME 2025",
    "gpqa_diamond_accuracy": "GPQA Diamond",
    "ifeval_prompt_strict": "IFEval prompt strict",
    "ifeval_prompt_loose": "IFEval prompt loose",
    "ifeval_instruction_strict": "IFEval instruction strict",
    "ifeval_instruction_loose": "IFEval instruction loose",
}
OVERVIEW = (
    "aime25_accuracy",
    "gpqa_diamond_accuracy",
    "ifeval_prompt_strict",
    "ifeval_instruction_strict",
)
IFEVAL = (
    "ifeval_prompt_strict",
    "ifeval_prompt_loose",
    "ifeval_instruction_strict",
    "ifeval_instruction_loose",
)


def render(rows: list[dict[str, str]], metric_ids: tuple[str, ...], output: Path, title: str) -> None:
    labels = list(dict.fromkeys((row["model_label"], row["reasoning_mode"]) for row in rows))
    lookup = {(row["model_label"], row["reasoning_mode"], row["metric_id"]): row for row in rows}
    x = np.arange(len(labels))
    width = min(0.72 / max(1, len(metric_ids)), 0.42)
    figure_width = max(11.5, len(labels) * 1.42)
    fig, axis = plt.subplots(figsize=(figure_width, 7.0))
    colors = plt.get_cmap("tab10").colors

    for index, metric_id in enumerate(metric_ids):
        offset = (index - (len(metric_ids) - 1) / 2) * width
        for label_index, label in enumerate(labels):
            row = lookup.get((*label, metric_id))
            if row is None:
                continue
            value = float(row["score"]) * 100
            qualified = row["result_status"] == "PASS_WITH_INVALID_OUTPUTS"
            bar = axis.bar(
                x[label_index] + offset,
                value,
                width,
                color=colors[index],
                hatch="///" if qualified else None,
                edgecolor="white" if qualified else colors[index],
                linewidth=0.8,
            )[0]
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                min(value + 1.2, 98.8),
                f"{value:.1f}{'†' if qualified else ''}",
                ha="center",
                va="bottom",
                fontsize=7.5,
                rotation=90 if len(metric_ids) > 1 else 0,
            )

    axis.set_xticks(x, [f"{model}\n{mode}" for model, mode in labels], rotation=22, ha="right")
    axis.set_ylabel("Score (%)")
    axis.set_ylim(0, 104)
    axis.grid(axis="y", alpha=0.25)
    legend = [Patch(facecolor=colors[i], label=METRICS[metric_id]) for i, metric_id in enumerate(metric_ids)]
    if any(row["result_status"] == "PASS_WITH_INVALID_OUTPUTS" for row in rows):
        legend.append(Patch(facecolor="white", edgecolor="gray", hatch="///", label="† invalid output(s) scored wrong"))
    fig.suptitle(title, y=0.86, fontweight="bold")
    fig.legend(handles=legend, ncol=2, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.995))
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scores", type=Path)
    parser.add_argument("output", type=Path, help="Canonical overview PNG path")
    args = parser.parse_args()
    rows = list(csv.DictReader(args.scores.open(encoding="utf-8", newline="")))
    rows = [row for row in rows if row["result_status"] in FINAL_STATUSES]
    if not rows:
        raise SystemExit("No finalized rows; refusing to render empty charts")

    render(rows, OVERVIEW, args.output, "Finalized capability benchmark comparison")
    render(rows, ("aime25_accuracy",), args.output.with_name("aime25-comparison.png"), "AIME 2025 — finalized scores")
    render(rows, ("gpqa_diamond_accuracy",), args.output.with_name("gpqa-diamond-comparison.png"), "GPQA Diamond — finalized robust scores")
    render(rows, IFEVAL, args.output.with_name("ifeval-comparison.png"), "IFEval — finalized scores")


if __name__ == "__main__":
    main()
