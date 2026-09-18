#!/usr/bin/env python3
"""Verify model discovery, chat completions, and vLLM tokenization."""

import json
import os
import sys
import time
import urllib.error
import urllib.request


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "EMPTY")
REQUESTED_MODEL = os.getenv("MODEL_ID", "").strip()
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "").strip()

if not REASONING_EFFORT:
    print(
        json.dumps(
            {
                "ok": False,
                "error": "REASONING_EFFORT must be set explicitly; model/template defaults are not benchmark-valid.",
            },
            indent=2,
        )
    )
    sys.exit(1)


def request_json(path: str, payload=None, timeout=20):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="GET" if payload is None else "POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body, time.perf_counter() - started


try:
    models, model_latency = request_json("/v1/models")
except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
    print(json.dumps({"ok": False, "base_url": BASE_URL, "error": str(exc)}, indent=2))
    sys.exit(2)

model_ids = [item.get("id") for item in models.get("data", []) if item.get("id")]
if REQUESTED_MODEL:
    model_id = REQUESTED_MODEL
elif len(model_ids) == 1:
    model_id = model_ids[0]
else:
    print(
        json.dumps(
            {
                "ok": False,
                "base_url": BASE_URL,
                "models": model_ids,
                "error": "Set MODEL_ID because the endpoint did not advertise exactly one model.",
            },
            indent=2,
        )
    )
    sys.exit(3)

try:
    completion, completion_latency = request_json(
        "/v1/chat/completions",
        {
            "model": model_id,
            "messages": [{"role": "user", "content": "Reply with exactly: BENCHMARK_READY"}],
            "temperature": 0,
            "max_tokens": 32,
            "reasoning_effort": REASONING_EFFORT,
        },
        timeout=120,
    )
    probe_text = completion["choices"][0]["message"].get("content", "")
    tokenized, tokenize_latency = request_json(
        "/tokenize",
        {"model": model_id, "messages": [{"role": "user", "content": "token probe"}]},
        timeout=120,
    )
    token_count = tokenized.get("count", len(tokenized.get("tokens", [])))
except (KeyError, OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
    print(
        json.dumps(
            {"ok": False, "base_url": BASE_URL, "model_id": model_id, "error": str(exc)},
            indent=2,
        )
    )
    sys.exit(4)

print(
    json.dumps(
        {
            "ok": True,
            "base_url": BASE_URL,
            "model_id": model_id,
            "reasoning_effort": REASONING_EFFORT,
            "advertised_models": model_ids,
            "models_latency_s": round(model_latency, 4),
            "completion_latency_s": round(completion_latency, 4),
            "tokenize_latency_s": round(tokenize_latency, 4),
            "token_probe_count": token_count,
            "probe_text": probe_text,
            "usage": completion.get("usage"),
        },
        indent=2,
    )
)
