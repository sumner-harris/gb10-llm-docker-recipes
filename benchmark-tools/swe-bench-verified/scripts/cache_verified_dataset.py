#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]


def read_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in (ROOT / "pins.env").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            pins[key] = value
    return pins


def main() -> None:
    pins = read_pins()
    revision = pins["VERIFIED_DATASET_REVISION"]
    dataset_dir = ROOT / "data" / "SWE-bench_Verified"
    dataset_dir.parent.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id="SWE-bench/SWE-bench_Verified",
        repo_type="dataset",
        revision=revision,
        local_dir=dataset_dir,
    )
    dataset = load_dataset(str(dataset_dir), split="test")
    instance_ids = list(dataset["instance_id"])
    if len(instance_ids) != 500 or len(set(instance_ids)) != 500:
        raise RuntimeError(
            f"Expected 500 unique Verified IDs, got {len(instance_ids)} rows "
            f"and {len(set(instance_ids))} unique IDs"
        )

    manifests = ROOT / "manifests"
    manifests.mkdir(exist_ok=True)
    ids_text = "\n".join(instance_ids) + "\n"
    (manifests / "verified_instance_ids.txt").write_text(ids_text, encoding="utf-8")
    manifest = {
        "dataset": "SWE-bench/SWE-bench_Verified",
        "revision": revision,
        "split": "test",
        "rows": len(instance_ids),
        "unique_instance_ids": len(set(instance_ids)),
        "instance_ids_sha256": hashlib.sha256(ids_text.encode()).hexdigest(),
        "dataset_fingerprint": dataset._fingerprint,
    }
    (manifests / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
