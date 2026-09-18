#!/usr/bin/env python3
"""Rescore logged AIME samples with transparent final-integer extraction."""

import argparse
import json
import re
from pathlib import Path


PATTERNS = (
    ("boxed", re.compile(r"\\boxed\s*\{\s*([0-9]{1,3})\s*\}")),
    (
        "answer_label",
        re.compile(
            r"(?i)(?:final\s+answer|answer)\s*(?:is|:|=)?\s*"
            r"(?:\\?\[|\$+)?\s*(?:\\boxed\s*\{\s*)?([0-9]{1,3})"
        ),
    ),
    ("bare_line", re.compile(r"(?m)^\s*(?:\$+)?([0-9]{1,3})(?:\$+)?[.!]?\s*$")),
)


def response_text(row):
    value = row.get("resps", "")
    while isinstance(value, list) and value:
        value = value[0]
    return value if isinstance(value, str) else str(value)


def extract_final_integer(text):
    candidates = []
    for priority, (name, pattern) in enumerate(PATTERNS):
        for match in pattern.finditer(text):
            candidates.append((match.end(), -priority, int(match.group(1)), name))
    if not candidates:
        return None, "not_found"
    _, _, value, method = max(candidates)
    return value, method


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("samples", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    with args.samples.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    audit = []
    for row in rows:
        text = response_text(row)
        predicted, method = extract_final_integer(text)
        target = int(str(row["target"]).strip())
        audit.append(
            {
                "doc_id": row.get("doc_id"),
                "target": target,
                "predicted": predicted,
                "correct": predicted == target,
                "extraction": method,
                "response_chars": len(text),
                "response_complete": predicted is not None,
            }
        )

    correct = sum(item["correct"] for item in audit)
    missing = sum(not item["response_complete"] for item in audit)
    result = {
        "metric": "aime_final_integer_exact_match",
        "samples": len(audit),
        "correct": correct,
        "accuracy": correct / len(audit) if audit else None,
        "missing_final_answer": missing,
        "source_samples": str(args.samples),
        "audit": audit,
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
