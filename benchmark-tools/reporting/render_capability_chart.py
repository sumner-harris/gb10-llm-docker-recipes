#!/usr/bin/env python3
"""Render the repository-wide grouped vertical capability chart."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


METRICS = (
    ("aime25_accuracy", "AIME 2025"),
    ("gpqa_diamond_accuracy", "GPQA Diamond"),
    ("ifeval_prompt_strict", "IFEval prompt strict"),
    ("ifeval_instruction_strict", "IFEval instruction strict"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scores", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.scores.open(encoding="utf-8", newline="")))
    rows = [row for row in rows if row["result_status"] == "PASS"]
    if not rows:
        raise SystemExit("No audited PASS rows; refusing to render an empty or provisional chart")
    labels = sorted({(row["model_label"], row["reasoning_mode"]) for row in rows})
    lookup = {(row["model_label"], row["reasoning_mode"], row["metric_id"]): float(row["score"]) for row in rows}
    x = np.arange(len(labels))
    width = 0.18
    fig, axis = plt.subplots(figsize=(max(10, len(labels) * 1.3), 6.5))
    for index, (metric_id, metric_label) in enumerate(METRICS):
        values = [lookup.get((*label, metric_id), np.nan) * 100 for label in labels]
        axis.bar(x + (index - 1.5) * width, values, width, label=metric_label)
    axis.set_xticks(x, [f"{model}\n{mode}" for model, mode in labels], rotation=20, ha="right")
    axis.set_ylabel("Score (%)")
    axis.set_ylim(0, 100)
    axis.set_title("Capability benchmark comparison (audited PASS results only)", fontweight="bold")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(args.output, dpi=170, bbox_inches="tight")


if __name__ == "__main__":
    main()
