#!/usr/bin/env python3
"""Regrade GPQA Diamond generations with an AA-compatible answer extractor.

lm-eval's GPQA flexible filter prefers the last parenthesized capital letter.
That can mistake an enumerated option or a chemistry stereodescriptor such as
``(Z)`` for the model's answer. This scorer preserves the harness-native
metric while making an explicit-final-answer-first extraction the reporting
metric. It never sends model traffic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCORER_VERSION = "gpqa_aa_compatible_v1"
TASK = "gpqa_diamond_cot_zeroshot"
# AA-compatible primary expression, with whitespace and Markdown markers kept
# separate so the common ``**Answer**: **B**`` form is accepted reliably.
PRIMARY = re.compile(r"(?i)[\*_]{0,2}Answer[\*_]{0,2}\s*[:：]\s*[\*_]{0,2}\s*([A-D])(?![a-zA-Z0-9])")
FALLBACKS: list[tuple[str, re.Pattern[str]]] = [
    ("boxed", re.compile(r"\\boxed\{[^}]*([A-D])[^}]*\}")),
    ("answer_is", re.compile(r"(?i)answer is ([A-D])(?![a-zA-Z0-9])")),
    ("answer_is_parenthesized", re.compile(r"(?i)answer is \(([A-D])\)")),
    ("choice_format", re.compile(r"([A-D])\)\s*[^A-D]*")),
    ("explicit_correct", re.compile(r"(?i)([A-D])\s+is\s+the\s+correct\s+answer")),
    ("standalone_end", re.compile(r"([A-D])\s*$")),
    ("letter_period", re.compile(r"([A-D])\s*\.")),
    ("letter_nonword", re.compile(r"([A-D])\s*[^\w]")),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matches(pattern: re.Pattern[str], text: str) -> list[dict[str, Any]]:
    return [{"letter": m.group(1).upper(), "start": m.start(), "match": m.group(0)} for m in pattern.finditer(text)]


def extract_answer(text: str) -> dict[str, Any]:
    """Apply AA's ordered extraction sequence, taking the last match per tier."""
    stripped = text.strip()
    direct = re.fullmatch(r"(?i)[\(\[\{]?\s*([A-D])\s*[\)\]\}]?[\.!]?", stripped)
    if direct:
        return {"answer": direct.group(1).upper(), "method": "single_letter", "candidates": [direct.group(1).upper()], "match": stripped}
    matches = _matches(PRIMARY, text)
    if matches:
        selected = matches[-1]
        return {"answer": selected["letter"], "method": "answer_colon", "candidates": [m["letter"] for m in matches], "match": selected["match"]}
    for name, pattern in FALLBACKS:
        matches = _matches(pattern, text)
        if matches:
            selected = matches[-1]
            return {"answer": selected["letter"], "method": name, "candidates": [m["letter"] for m in matches], "match": selected["match"]}
    return {"answer": None, "method": "no_extraction", "candidates": [], "match": None}


def _find_one(run_dir: Path, pattern: str) -> Path:
    matches = sorted(run_dir.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {pattern!r} below {run_dir}, found {len(matches)}")
    return matches[0]


def _native_summary(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    task_result = result["results"][TASK]
    total = int(task_result["sample_len"])
    score = float(task_result["exact_match,flexible-extract"])
    return {"metric": "exact_match,flexible-extract", "score": score, "correct_derived": round(score * total), "total": total, "source_file": result_path.name, "source_sha256": sha256_file(result_path), "task_version": result.get("versions", {}).get(TASK), "status": "PRE_CORRECTION_HARNESS_NATIVE_RETAINED"}


def _load_unique_samples(sample_path: Path) -> dict[int, dict[str, Any]]:
    samples: dict[int, dict[str, Any]] = {}
    # Iterate physical LF-delimited records. str.splitlines() also splits on
    # Unicode NEL/line-separator characters that can legitimately occur inside
    # a JSON string in a model response, corrupting otherwise valid JSONL.
    with sample_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            doc_id = int(row["doc_id"])
            if doc_id in samples:
                prior = samples[doc_id]
                if prior.get("resps") != row.get("resps") or prior.get("target") != row.get("target"):
                    raise RuntimeError(f"duplicate doc_id {doc_id} disagrees across lm-eval filter rows")
                continue
            samples[doc_id] = row
    return samples


def _invalid_doc_ids(run_dir: Path) -> tuple[set[int], dict[str, Any]]:
    audit_path = run_dir / "strict_audit.json"
    if not audit_path.exists():
        return set(), {"status": "NOT_AVAILABLE", "source_file": None, "gate": None}
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    invalid = {int(value) for value in audit.get("cap_doc_ids", [])}
    invalid_indices = set(audit.get("null_content_response_indices", [])) | set(audit.get("empty_content_response_indices", [])) | set(audit.get("cap_response_indices", []))
    for response in audit.get("responses", []):
        if response.get("index") in invalid_indices:
            invalid.update(int(value) for value in response.get("matched_doc_ids", []))
    return invalid, {"status": "AVAILABLE", "source_file": audit_path.name, "source_sha256": sha256_file(audit_path), "gate": audit.get("gate"), "invalid_doc_ids_scored_incorrect": sorted(invalid)}


def score_run(run_dir: Path) -> dict[str, Any]:
    sample_path = _find_one(run_dir, "lm_eval/**/samples_gpqa_diamond_cot_zeroshot_*.jsonl")
    result_path = _find_one(run_dir, "lm_eval/**/results_*.json")
    samples = _load_unique_samples(sample_path)
    native = _native_summary(result_path)
    invalid_doc_ids, integrity = _invalid_doc_ids(run_dir)
    if len(samples) != native["total"]:
        raise RuntimeError(f"unique samples {len(samples)} != native total {native['total']}")
    evidence, methods = [], {}
    correct = extracted = 0
    for doc_id in sorted(samples):
        sample = samples[doc_id]
        raw = sample.get("resps", [[""]])
        response = raw[0][0] if raw and raw[0] else ""
        extraction = extract_answer(response)
        answer = extraction["answer"]
        gold_match = re.search(r"([A-D])", str(sample.get("target", "")))
        gold = gold_match.group(1) if gold_match else None
        is_invalid = doc_id in invalid_doc_ids
        is_correct = bool(answer and gold and answer == gold and not is_invalid)
        extracted += int(answer is not None)
        correct += int(is_correct)
        methods[extraction["method"]] = methods.get(extraction["method"], 0) + 1
        evidence.append({"doc_id": doc_id, "gold": gold, "extracted": answer, "method": extraction["method"], "candidates_in_selected_tier": extraction["candidates"], "selected_match": extraction["match"], "invalid_output_forced_incorrect": is_invalid, "correct": is_correct, "response_sha256": hashlib.sha256(response.encode("utf-8")).hexdigest()})
    total = len(samples)
    return {"schema_version": 1, "scorer_version": SCORER_VERSION, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "task": TASK, "metric": "gpqa_diamond_accuracy_aa_compatible_v1", "score": correct / total, "correct": correct, "total": total, "extracted": extracted, "missing_extraction": total - extracted, "method_counts": methods, "invalid_outputs_scored_incorrect": sorted(invalid_doc_ids), "integrity": integrity, "source_samples": {"file": sample_path.name, "sha256": sha256_file(sample_path)}, "native_lm_eval": native, "per_doc": evidence, "extraction_policy": {"basis": "Artificial Analysis published GPQA extraction order, restricted to A-D", "selection": "first matching tier; last match within that tier", "priority": ["single_letter", "answer_colon"] + [name for name, _ in FALLBACKS], "invalid_output_policy": "strict-audit capped/null/empty outputs are scored incorrect without retry"}, "reporting_status": "PRIMARY_CORRECTED_ROBUST"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", default="gpqa_score_robust_aa_v1.json")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    corrected = score_run(run_dir)
    native = corrected["native_lm_eval"]
    native_path = run_dir / "gpqa_score_native_lm_eval_precorrection.json"
    robust_path = run_dir / args.output
    primary_path = run_dir / "gpqa_score_primary.json"
    native_path.write_text(json.dumps(native, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    robust_path.write_text(json.dumps(corrected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    primary = {"primary_metric": corrected["metric"], "primary_artifact": robust_path.name, "score": corrected["score"], "correct": corrected["correct"], "total": corrected["total"], "harness_native_metric_retained": native["metric"], "harness_native_artifact": native_path.name, "harness_native_score": native["score"], "scorer_version": SCORER_VERSION}
    primary_path.write_text(json.dumps(primary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(primary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
