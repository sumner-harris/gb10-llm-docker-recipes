#!/usr/bin/env python3
"""Regression tests for gated access and shell exit-code handling."""

import json
import os
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SUITE_DIR = Path(__file__).resolve().parents[1]


class GPQAControlFlowTests(unittest.TestCase):
    def test_builder_denial_is_blocked_when_repository_metadata_is_public(self):
        class DatasetNotFoundError(Exception):
            pass

        datasets = types.ModuleType("datasets")
        dataset_errors = types.ModuleType("datasets.exceptions")
        dataset_errors.DatasetNotFoundError = DatasetNotFoundError

        def denied_builder(*_args, **_kwargs):
            raise DatasetNotFoundError("simulated gated data denial")

        datasets.load_dataset_builder = denied_builder

        hub = types.ModuleType("huggingface_hub")
        hub_errors = types.ModuleType("huggingface_hub.errors")
        for name in (
            "GatedRepoError",
            "HfHubHTTPError",
            "LocalTokenNotFoundError",
            "RepositoryNotFoundError",
        ):
            setattr(hub_errors, name, type(name, (Exception,), {}))

        modules = {
            "datasets": datasets,
            "datasets.exceptions": dataset_errors,
            "huggingface_hub": hub,
            "huggingface_hub.errors": hub_errors,
        }
        with tempfile.TemporaryDirectory() as directory:
            status_file = Path(directory) / "gpqa_access.json"
            argv = ["check_gpqa_access.py", str(status_file)]
            with patch.dict(sys.modules, modules), patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as raised:
                    runpy.run_path(
                        str(SUITE_DIR / "scripts" / "check_gpqa_access.py"),
                        run_name="__main__",
                    )
            self.assertEqual(raised.exception.code, 10)
            status = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "BLOCKED")
            self.assertEqual(status["dataset"], "Idavidrein/gpqa")
            self.assertEqual(status["dataset_config"], "gpqa_diamond")
            self.assertNotIn("simulated gated data denial", json.dumps(status))

    def test_gpqa_wrapper_propagates_lm_eval_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            scripts = fixture / "scripts"
            venv_bin = fixture / ".venv" / "bin"
            run_dir = fixture / "results" / "test"
            scripts.mkdir(parents=True)
            venv_bin.mkdir(parents=True)
            run_dir.mkdir(parents=True)

            runner = scripts / "run_gpqa.sh"
            runner.write_text(
                (SUITE_DIR / "scripts" / "run_gpqa.sh").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            checker_python = venv_bin / "python"
            checker_python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            checker_python.chmod(0o755)
            lm_eval = scripts / "run_lm_eval.sh"
            lm_eval.write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")

            environment = os.environ.copy()
            environment.update({"RUN_DIR": str(run_dir), "RUN_GPQA": "auto"})
            completed = subprocess.run(
                ["bash", str(runner)],
                cwd=fixture,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 7)
            status = (run_dir / "lm_eval_status.txt").read_text(encoding="utf-8")
            self.assertIn("lm-eval exited with status 7", status)

    def test_lm_eval_runner_returns_nonzero_when_task_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            scripts = fixture / "scripts"
            venv_bin = fixture / ".venv" / "bin"
            run_dir = fixture / "results" / "test"
            scripts.mkdir(parents=True)
            venv_bin.mkdir(parents=True)
            run_dir.mkdir(parents=True)

            runner = scripts / "run_lm_eval.sh"
            runner.write_text(
                (SUITE_DIR / "scripts" / "run_lm_eval.sh").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            lm_eval = venv_bin / "lm-eval"
            lm_eval.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"ls\" ]]; then printf '|aime25 |\n'; exit 0; fi\n"
                "printf '%s\\n' \"$@\" > \"$RUN_DIR/lm_eval_invocation.txt\"\n"
                "exit 23\n",
                encoding="utf-8",
            )
            lm_eval.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                {
                    "RUN_DIR": str(run_dir),
                    "MODEL_ID": "test-model",
                    "EVAL_TASKS": "aime25",
                }
            )
            completed = subprocess.run(
                ["bash", str(runner)],
                cwd=fixture,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            status = (run_dir / "lm_eval_status.txt").read_text(encoding="utf-8")
            self.assertIn("FAIL aime25", status)
            invocation = (run_dir / "lm_eval_invocation.txt").read_text(encoding="utf-8")
            self.assertIn("timeout=10800", invocation)
            self.assertIn("max_gen_toks=65536", invocation)

    def test_capability_and_performance_timeouts_are_separate(self):
        config = (SUITE_DIR / "config.env.example").read_text(encoding="utf-8")
        self.assertIn("EVAL_TIMEOUT=10800", config)
        self.assertIn("PERF_TIMEOUT=3600", config)
        performance_runner = (SUITE_DIR / "scripts" / "run_perf.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('os.getenv("PERF_TIMEOUT", "3600")', performance_runner)
        self.assertNotIn('os.getenv("EVAL_TIMEOUT"', performance_runner)


if __name__ == "__main__":
    unittest.main()
