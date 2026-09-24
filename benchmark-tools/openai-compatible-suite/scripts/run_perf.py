#!/usr/bin/env python3
"""Resumable exact-token throughput matrix for an OpenAI-compatible vLLM API."""

import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import httpx
from openai import AsyncOpenAI


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "EMPTY")
MODEL_ID = os.getenv("MODEL_ID", "").strip()
RUN_DIR = Path(os.environ.get("RUN_DIR", "results/manual"))
REQUESTS = int(os.getenv("PERF_REQUESTS", "24"))
CONCURRENCIES = [int(value) for value in os.getenv("PERF_CONCURRENCIES", "1,4,8").split(",")]
TIMEOUT = float(os.getenv("PERF_TIMEOUT", "3600"))
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "").strip()

SCENARIOS = [
    {"name": "interactive", "prompt_tokens": 512, "output_tokens": 256},
    {"name": "long_context", "prompt_tokens": 8192, "output_tokens": 1024},
    {"name": "long_generation", "prompt_tokens": 32768, "output_tokens": 4096},
]


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def percentile(values, pct):
    ordered = sorted(values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * pct / 100
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


async def discover_model(client):
    if MODEL_ID:
        return MODEL_ID
    page = await client.models.list()
    model_ids = [item.id for item in page.data]
    if len(model_ids) != 1:
        raise RuntimeError("Set MODEL_ID; endpoint must advertise exactly one model")
    return model_ids[0]


async def chat_token_count(client, model_id, prompt):
    response = await client.post(
        BASE_URL + "/tokenize",
        json={"model": model_id, "messages": [{"role": "user", "content": prompt}]},
    )
    response.raise_for_status()
    payload = response.json()
    return int(payload.get("count", len(payload.get("tokens", []))))


async def calibrated_prompt(client, model_id, target_tokens):
    """Find a synthetic prompt whose rendered chat request is exactly target_tokens."""
    for unit in (" benchmark", " x", " data", "0", ".", "\n"):
        low, high = 0, target_tokens * 2
        while low < high:
            middle = (low + high + 1) // 2
            count = await chat_token_count(client, model_id, unit * middle)
            if count <= target_tokens:
                low = middle
            else:
                high = middle - 1
        start = max(0, low - 8)
        for repeats in range(start, low + 33):
            prompt = unit * repeats
            count = await chat_token_count(client, model_id, prompt)
            if count == target_tokens:
                return prompt, count
            if count > target_tokens:
                break
    raise RuntimeError(
        f"Could not synthesize an exact {target_tokens}-token chat prompt with this tokenizer"
    )


def delta_text(delta):
    content = delta.content or ""
    extra = delta.model_extra or {}
    reasoning = extra.get("reasoning") or extra.get("reasoning_content") or ""
    return reasoning + content


async def one_request(client, model_id, prompt, output_tokens, semaphore, request_index):
    async with semaphore:
        started = time.perf_counter()
        first_token = None
        output_chars = 0
        usage = None
        finish_reason = None
        try:
            stream = await client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=output_tokens,
                stream=True,
                stream_options={"include_usage": True},
                extra_body={
                    "ignore_eos": True,
                    "reasoning_effort": REASONING_EFFORT,
                },
            )
            async for event in stream:
                if event.usage is not None:
                    usage = event.usage.model_dump()
                if event.choices:
                    if event.choices[0].finish_reason is not None:
                        finish_reason = event.choices[0].finish_reason
                    text = delta_text(event.choices[0].delta)
                    if text:
                        if first_token is None:
                            first_token = time.perf_counter()
                        output_chars += len(text)
            ended = time.perf_counter()
            return {
                "ok": True,
                "request_index": request_index,
                "ttft_s": None if first_token is None else first_token - started,
                "e2e_s": ended - started,
                "output_chars": output_chars,
                "usage": usage,
                "finish_reason": finish_reason,
            }
        except Exception as exc:  # Preserve failures as row-level raw evidence.
            return {
                "ok": False,
                "request_index": request_index,
                "e2e_s": time.perf_counter() - started,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }


def rebuild_aggregates(performance_dir):
    cells = []
    requests = []
    for cell_path in sorted((performance_dir / "cells").glob("*.json")):
        cell = json.loads(cell_path.read_text(encoding="utf-8"))
        cells.append(cell["summary"])
        for request in cell["requests"]:
            requests.append(request)
    atomic_json(RUN_DIR / "performance.json", cells)
    request_path = RUN_DIR / "performance_requests.jsonl"
    temporary = request_path.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for request in requests:
            handle.write(json.dumps(request) + "\n")
    temporary.replace(request_path)


def validate_cell(summary, cell_path):
    requests = int(summary["requests"])
    successes = int(summary["successes"])
    failures = int(summary["failures"])
    exact = int(summary["exact_output_count"])
    if successes != requests or failures != 0 or exact != requests:
        raise RuntimeError(
            f"Invalid throughput cell {cell_path}: successes={successes}/{requests}, "
            f"failures={failures}, exact_output_count={exact}. The raw cell was retained; "
            "move it to a quarantine directory before rerunning."
        )


async def main():
    if not REASONING_EFFORT:
        raise RuntimeError(
            "REASONING_EFFORT must be set explicitly; model/template defaults are not benchmark-valid"
        )
    performance_dir = RUN_DIR / "performance"
    cell_dir = performance_dir / "cells"
    cell_dir.mkdir(parents=True, exist_ok=True)
    api_client = AsyncOpenAI(base_url=BASE_URL + "/v1", api_key=API_KEY, timeout=TIMEOUT)
    model_id = await discover_model(api_client)
    run_config = {
        "model_id": model_id,
        "base_url": BASE_URL,
        "requests_per_cell": REQUESTS,
        "concurrencies": CONCURRENCIES,
        "scenarios": SCENARIOS,
        "temperature": 0,
        "reasoning_effort": REASONING_EFFORT,
        "ignore_eos": True,
    }
    config_path = performance_dir / "run_config.json"
    if config_path.exists():
        previous = json.loads(config_path.read_text(encoding="utf-8"))
        if previous != run_config:
            raise RuntimeError("Resume refused: performance/run_config.json does not match")
    else:
        atomic_json(config_path, run_config)

    headers = {"Authorization": f"Bearer {API_KEY}"}
    async with httpx.AsyncClient(timeout=120, headers=headers) as http_client:
        for scenario in SCENARIOS:
            prompt, calibrated_tokens = await calibrated_prompt(
                http_client, model_id, scenario["prompt_tokens"]
            )
            for concurrency in CONCURRENCIES:
                cell_path = cell_dir / f"{scenario['name']}_c{concurrency}.json"
                if cell_path.exists():
                    retained = json.loads(cell_path.read_text(encoding="utf-8"))
                    validate_cell(retained["summary"], cell_path)
                    print(json.dumps({"resumed_cell": str(cell_path)}), flush=True)
                    continue
                semaphore = asyncio.Semaphore(concurrency)
                wall_started = time.perf_counter()
                results = await asyncio.gather(
                    *[
                        one_request(
                            api_client,
                            model_id,
                            prompt,
                            scenario["output_tokens"],
                            semaphore,
                            request_index,
                        )
                        for request_index in range(REQUESTS)
                    ]
                )
                wall_s = time.perf_counter() - wall_started
                successes = [item for item in results if item["ok"]]
                failures = [item for item in results if not item["ok"]]
                ttfts = [item["ttft_s"] for item in successes if item["ttft_s"] is not None]
                e2es = [item["e2e_s"] for item in successes]
                completion_counts = [
                    (item.get("usage") or {}).get("completion_tokens", 0)
                    for item in successes
                ]
                finish_reasons = {}
                for item in successes:
                    reason = item.get("finish_reason") or "unknown"
                    finish_reasons[reason] = finish_reasons.get(reason, 0) + 1
                exact_output_count = sum(
                    count == scenario["output_tokens"] for count in completion_counts
                )
                summary = {
                    "model_id": model_id,
                    "scenario": scenario,
                    "calibrated_prompt_tokens": calibrated_tokens,
                    "concurrency": concurrency,
                    "requests": REQUESTS,
                    "successes": len(successes),
                    "failures": len(failures),
                    "exact_output_count": exact_output_count,
                    "finish_reasons": finish_reasons,
                    "wall_s": wall_s,
                    "request_throughput_rps": len(successes) / wall_s if wall_s else None,
                    "output_throughput_tok_s": sum(completion_counts) / wall_s if wall_s else None,
                    "ttft_p50_s": percentile(ttfts, 50),
                    "ttft_p95_s": percentile(ttfts, 95),
                    "e2e_p50_s": percentile(e2es, 50),
                    "e2e_p95_s": percentile(e2es, 95),
                    "e2e_mean_s": statistics.fmean(e2es) if e2es else None,
                    "output_tokens": sum(completion_counts),
                }
                for item in results:
                    item.update(
                        scenario=scenario["name"],
                        concurrency=concurrency,
                        prompt_tokens=calibrated_tokens,
                        requested_output_tokens=scenario["output_tokens"],
                        reasoning_effort=REASONING_EFFORT,
                    )
                atomic_json(cell_path, {"summary": summary, "requests": results})
                rebuild_aggregates(performance_dir)
                print(json.dumps(summary), flush=True)
                validate_cell(summary, cell_path)

    rebuild_aggregates(performance_dir)


if __name__ == "__main__":
    asyncio.run(main())
