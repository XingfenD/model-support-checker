"""Regression tests for the machine-readable ``--json`` report."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

from src.cli import build_report
from src.state.constants import STATE_FILE

from tests.helpers import commit, init_repo, tag, write


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG = (
    'if values.get("architectures") == ["DeepseekV41ForCausalLM"]:\n'
    '    values["architectures"] = ["DeepseekV4ForCausalLM"]\n'
)
MODEL = "class DeepseekV4ForCausalLM:\n    pass\nEntryClass = [DeepseekV4ForCausalLM]\n"


class JsonReportTests(unittest.TestCase):
    def test_build_report_is_json_serializable(self):
        report = build_report(
            model="org/model",
            arch="DeepseekV41ForCausalLM",
            archs=["DeepseekV41ForCausalLM"],
            arch_source="manual",
            entries={
                "sglang": {
                    "label": "SGLang",
                    "supported": True,
                    "file": "python/sglang/srt/models/deepseek_v4.py",
                    "version": "v0.5.21",
                    "version_basis": "first stable release containing the implementation commit",
                    "docs": "no",
                    "registry": None,
                    "remap": {
                        "from": "DeepseekV41ForCausalLM",
                        "to": "DeepseekV4ForCausalLM",
                        "file": "python/sglang/srt/configs/deepseek_v41.py",
                    },
                }
            },
            freshness={"sglang": {"path": "/tmp/sglang", "behind": 3}},
        )

        decoded = json.loads(json.dumps(report))
        self.assertEqual(decoded["model"], "org/model")
        self.assertEqual(
            decoded["frameworks"]["sglang"]["remap"]["to"],
            "DeepseekV4ForCausalLM",
        )
        self.assertEqual(decoded["freshness"]["sglang"]["behind"], 3)

    @unittest.skipUnless(
        os.path.exists(STATE_FILE),
        "CLI integration test needs an initialized .state/state.json",
    )
    def test_cli_json_output_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as repo:
            init_repo(repo)
            write(
                repo,
                "python/sglang/srt/configs/deepseek_v41.py",
                CONFIG,
            )
            write(
                repo,
                "python/sglang/srt/models/deepseek_v4.py",
                MODEL,
            )
            commit(repo, "add DeepSeek V4.1 support")
            tag(repo, "v0.5.21")

            proc = subprocess.run(
                [
                    sys.executable,
                    "main.py",
                    "--framework",
                    "sglang",
                    "--arch",
                    "DeepseekV41ForCausalLM",
                    "--sglang-path",
                    repo,
                    "--no-docs",
                    "--json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            entry = report["frameworks"]["sglang"]
            self.assertTrue(entry["supported"])
            self.assertEqual(
                entry["file"],
                "python/sglang/srt/models/deepseek_v4.py",
            )
            self.assertEqual(entry["remap"]["to"], "DeepseekV4ForCausalLM")
            self.assertEqual(entry["version"], "v0.5.21")
            self.assertNotIn("revert", entry)


if __name__ == "__main__":
    unittest.main()
