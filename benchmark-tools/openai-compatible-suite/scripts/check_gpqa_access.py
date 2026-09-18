#!/usr/bin/env python3
"""Check official GPQA dataset entitlement without exposing credentials."""

import argparse
import json
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.errors import (
    GatedRepoError,
    HfHubHTTPError,
    LocalTokenNotFoundError,
    RepositoryNotFoundError,
)


DATASET_ID = "Idavidrein/gpqa"
TASK = "gpqa_diamond_cot_zeroshot"
ACCESS_URL = "https://huggingface.co/datasets/Idavidrein/gpqa"


def write_status(path, status, reason):
    result = {
        "status": status,
        "task": TASK,
        "dataset": DATASET_ID,
        "reason": reason,
    }
    if status == "BLOCKED":
        result["instructions"] = [
            f"Visit {ACCESS_URL} while signed in and accept/request the dataset license.",
            "Authenticate the benchmark host with `hf auth login` or set HF_TOKEN in the process environment.",
            "Rerun scripts/run_gpqa.sh with the same RUN_DIR after access is granted.",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("status_file", type=Path)
    args = parser.parse_args()

    try:
        # token=True requires a cached login or HF_TOKEN. dataset_info then
        # verifies that the authenticated identity has accepted the gate.
        HfApi().dataset_info(DATASET_ID, token=True)
    except LocalTokenNotFoundError:
        write_status(args.status_file, "BLOCKED", "No Hugging Face authentication was found.")
        return 10
    except (GatedRepoError, RepositoryNotFoundError) as exc:
        write_status(
            args.status_file,
            "BLOCKED",
            f"The authenticated identity cannot access the gated dataset ({type(exc).__name__}).",
        )
        return 10
    except HfHubHTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (401, 403):
            write_status(
                args.status_file,
                "BLOCKED",
                f"Hugging Face denied dataset access with HTTP {status_code}.",
            )
            return 10
        write_status(
            args.status_file,
            "ERROR",
            f"Hugging Face access check failed with HTTP {status_code or 'unknown'}.",
        )
        return 2
    except OSError as exc:
        write_status(
            args.status_file,
            "ERROR",
            f"Hugging Face access check could not reach the service ({type(exc).__name__}).",
        )
        return 2

    write_status(args.status_file, "ACCESSIBLE", "Official gated dataset access verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
