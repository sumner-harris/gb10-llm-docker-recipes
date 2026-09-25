#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    predictions = json.loads(args.source.read_text(encoding="utf-8"))
    if not isinstance(predictions, dict):
        raise TypeError("Expected SWE-agent preds.json to contain an object")

    rows = []
    for instance_id, prediction in sorted(predictions.items()):
        if not isinstance(prediction, dict):
            raise TypeError(f"Prediction for {instance_id} is not an object")
        patch = prediction.get("model_patch")
        if patch is None:
            patch = prediction.get("submission")
        rows.append(
            {
                "instance_id": instance_id,
                "model_name_or_path": prediction.get("model_name_or_path", "local-vllm"),
                "model_patch": patch or "",
            }
        )

    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} predictions to {args.destination}")


if __name__ == "__main__":
    main()
