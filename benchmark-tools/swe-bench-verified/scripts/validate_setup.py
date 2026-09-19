#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
YAML_LOADER = YAML(typ="safe")

EXPECTED_MODES = {
    "qwen_off": ("openai/qwen3.8-flash-next", "none"),
    "qwen_low": ("openai/qwen3.8-flash-next", "low"),
    "qwen_medium": ("openai/qwen3.8-flash-next", "medium"),
    "qwen_xhigh": ("openai/qwen3.8-flash-next", "xhigh"),
    "mistral_none": ("openai/mistral-small-4-119b-nvfp4", "none"),
    "mistral_high": ("openai/mistral-small-4-119b-nvfp4", "high"),
    "nemotron_off": ("openai/nemotron-3-super-120b-nvfp4", "none"),
    "nemotron_low": ("openai/nemotron-3-super-120b-nvfp4", "low"),
    "nemotron_regular": ("openai/nemotron-3-super-120b-nvfp4", "high"),
}


def pins() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in (ROOT / "pins.env").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def main() -> None:
    pinned = pins()
    assert git_head(ROOT / "vendor" / "SWE-bench") == pinned["SWEBENCH_COMMIT"]
    assert git_head(ROOT / "vendor" / "SWE-agent") == pinned["SWEAGENT_COMMIT"]

    manifest = json.loads(
        (ROOT / "manifests" / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["revision"] == pinned["VERIFIED_DATASET_REVISION"]
    assert manifest["rows"] == 500
    assert manifest["unique_instance_ids"] == 500

    common = YAML_LOADER.load(ROOT / "configs" / "agent_common.yaml")
    assert common["instances"]["subset"] == "verified"
    assert common["instances"]["split"] == "test"
    assert common["instances"]["evaluate"] is False
    assert common["num_workers"] == 1
    # SWE-ReX controls the task container through a published localhost port.
    # Docker's network=none makes that control plane unreachable.
    assert "--network=none" not in common["instances"]["deployment"].get(
        "docker_args", []
    )

    for mode, (model_name, effort) in EXPECTED_MODES.items():
        config = YAML_LOADER.load(ROOT / "configs" / "modes" / f"{mode}.yaml")
        model = config["agent"]["model"]
        kwargs = model["completion_kwargs"]
        assert model["name"] == model_name
        assert "api_base" not in model
        assert model["api_key"] == "$VLLM_API_KEY"
        assert model["temperature"] == 0
        assert model["per_instance_call_limit"] == 100
        assert kwargs["reasoning_effort"] == effort
        assert kwargs["seed"] == 1234
        assert kwargs["max_tokens"] == 65536

        template = kwargs.get("extra_body", {}).get("chat_template_kwargs")
        if mode.startswith("qwen_"):
            assert template["preserve_thinking"] is False
            assert template["enable_thinking"] is (mode != "qwen_off")
        elif mode.startswith("nemotron_"):
            expected = {
                "nemotron_off": (False, False),
                "nemotron_low": (True, True),
                "nemotron_regular": (True, False),
            }[mode]
            assert (template["enable_thinking"], template["low_effort"]) == expected
        else:
            assert template is None

    assert not (ROOT / "run-authorization").exists(), (
        "run-authorization exists; remove it until a benchmark is intentionally approved"
    )

    endpoint_example = (ROOT / "endpoints.env.example").read_text(encoding="utf-8")
    assert "10." not in endpoint_example
    assert "QWEN_API_BASE=" in endpoint_example
    assert "MISTRAL_API_BASE=" in endpoint_example
    assert "NEMOTRON_API_BASE=" in endpoint_example

    docker_access = subprocess.run(
        ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0
    report = {
        "status": "CONFIGURED_NOT_RUN",
        "host_architecture": platform.machine(),
        "official_x86_64_recommended": True,
        "docker_access_for_current_user": docker_access,
        "mode_configs": len(EXPECTED_MODES),
        "verified_instances": 500,
        "authorization_sentinel_present": False,
        "inference_requests_sent": 0,
        "evaluation_containers_started": 0,
    }
    (ROOT / "manifests" / "setup_validation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
