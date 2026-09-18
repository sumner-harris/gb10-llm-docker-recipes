#!/usr/bin/env python3
"""Token-count saved lm-eval responses and flag likely generation-cap hits."""

import argparse
import json
import os
from pathlib import Path

import httpx


def response_text(row):
    value = row.get("resps", "")
    while isinstance(value, list) and value:
        value = value[0]
    if value is None or isinstance(value, list):
        return ""
    return value if isinstance(value, str) else str(value)


def discover_model(client, base_url):
    response = client.get(base_url.rstrip("/") + "/v1/models")
    response.raise_for_status()
    model_ids = [item["id"] for item in response.json().get("data", [])]
    if len(model_ids) != 1:
        raise RuntimeError("Set MODEL_ID; endpoint must advertise exactly one model")
    return model_ids[0]


def tokenize(client, base_url, model_id, text):
    response = client.post(
        base_url.rstrip("/") + "/tokenize",
        json={"model": model_id, "prompt": text},
    )
    response.raise_for_status()
    payload = response.json()
    if "count" in payload:
        return int(payload["count"])
    if "tokens" in payload:
        return len(payload["tokens"])
    raise RuntimeError(f"Unrecognized /tokenize response fields: {sorted(payload)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()

    base_url = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
    api_key = os.environ.get("API_KEY", "EMPTY")
    model_id = os.environ.get("MODEL_ID", "").strip()
    generation_ceiling = int(os.environ.get("MAX_GEN_TOKS", "130000"))
    request_timeout = float(os.environ.get("EVAL_TIMEOUT", "21600"))
    sample_files = sorted((args.run_dir / "lm_eval").glob("*/*/samples_*.jsonl"))
    if not sample_files:
        raise SystemExit(f"No lm-eval sample files found below {args.run_dir}")

    records = []
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=request_timeout, headers=headers) as client:
        if not model_id:
            model_id = discover_model(client, base_url)
        for sample_file in sample_files:
            task = sample_file.parent.parent.name
            with sample_file.open(encoding="utf-8") as handle:
                for line in handle:
                    row = json.loads(line)
                    text = response_text(row)
                    token_count = tokenize(client, base_url, model_id, text)
                    records.append(
                        {
                            "task": task,
                            "doc_id": row.get("doc_id"),
                            "response_chars": len(text),
                            "response_tokens": token_count,
                            "invalid_empty_response": not text.strip(),
                            "suspected_length_limited": token_count >= generation_ceiling - 8,
                        }
                    )

    by_task = {}
    for task in sorted({item["task"] for item in records}):
        task_records = [item for item in records if item["task"] == task]
        by_task[task] = {
            "responses": len(task_records),
            "suspected_length_limited": sum(
                item["suspected_length_limited"] for item in task_records
            ),
            "invalid_empty_responses": sum(
                item["invalid_empty_response"] for item in task_records
            ),
            "largest_responses": sorted(
                task_records, key=lambda item: item["response_tokens"], reverse=True
            )[:10],
        }

    report = {
        "model_id": model_id,
        "generation_ceiling_tokens": generation_ceiling,
        "heuristic": "raw response token count >= generation ceiling - 8",
        "tasks": by_task,
        "responses": records,
    }
    output = args.run_dir / "capability_output_audit.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "tasks": by_task}, indent=2))
    invalid = [
        item
        for item in records
        if item["invalid_empty_response"] or item["suspected_length_limited"]
    ]
    if invalid:
        raise SystemExit(
            "Capability audit found empty or generation-limited responses; "
            "recover them before treating capability scores as final"
        )


if __name__ == "__main__":
    main()
