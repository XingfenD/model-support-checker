"""Regression tests for reverted-then-relanded support detection.

A local snapshot can contain a revert commit even though upstream main has
already re-landed the support (vLLM-Ascend PR #16544 -> revert #16905).
Reporting a flat NO from that snapshot is misleading.
"""

import tempfile
import unittest

from src.framework_strategies.vllm_ascend import VllmAscendStrategy

from tests.helpers import commit, git, init_repo, write


MODEL = "class AscendDeepseekV41ForCausalLM:\n    pass\n"

REGISTRY_BEFORE = (
    "_CUSTOMIZED_MODEL_ARCHS = {\n"
    '    "DeepseekV41ForCausalLM": '
    '"vllm_ascend.models.deepseek_v41.vl_model:'
    'AscendDeepseekV41ForCausalLM",\n'
    "}\n"
)

REGISTRY_AFTER = "_CUSTOMIZED_MODEL_ARCHS = {}\n"


class RevertDetectionTests(unittest.TestCase):
    def test_detects_revert_that_removes_arch(self):
        with tempfile.TemporaryDirectory() as repo:
            init_repo(repo)
            write(repo, "README.md", "start\n")
            commit(repo, "initial")
            write(
                repo,
                "vllm_ascend/models/deepseek_v41/vl_model.py",
                MODEL,
            )
            write(repo, "vllm_ascend/models/__init__.py", REGISTRY_BEFORE)
            commit(repo, "add DeepSeek V4.1 support (#16544)")

            write(repo, "vllm_ascend/models/__init__.py", REGISTRY_AFTER)
            git(repo, "rm", "-q", "vllm_ascend/models/deepseek_v41/vl_model.py")
            commit(
                repo,
                'Revert "[Feature] Add DeepSeek V4.1 framework support (#16544)"',
                date="2026-09-18T00:00:00+00:00",
            )

            strategy = VllmAscendStrategy()
            ctx = strategy.make_context(repo)
            info = strategy.detect_revert("DeepseekV41ForCausalLM", ctx)

            self.assertIsNotNone(info)
            self.assertIn("DeepSeek V4.1", info["subject"])
            self.assertRegex(info["commit"], r"^[0-9a-f]{7,}$")

    def test_returns_none_when_no_revert_exists(self):
        with tempfile.TemporaryDirectory() as repo:
            init_repo(repo)
            write(repo, "vllm_ascend/models/deepseek_v41/vl_model.py", MODEL)
            commit(repo, "add support")

            strategy = VllmAscendStrategy()
            ctx = strategy.make_context(repo)

            self.assertIsNone(
                strategy.detect_revert("DeepseekV41ForCausalLM", ctx)
            )


if __name__ == "__main__":
    unittest.main()
