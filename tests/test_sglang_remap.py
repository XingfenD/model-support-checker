"""Regression tests for SGLang architecture remaps.

SGLang normalizes some HF architecture names before dispatching to a model
class.  DeepSeek-V4.1 is the canonical example::

    if values.get("architectures") == ["DeepseekV41ForCausalLM"]:
        values["architectures"] = ["DeepseekV4ForCausalLM"]

A plain grep for ``DeepseekV41ForCausalLM`` under ``models/`` therefore
returns a false NO.
"""

import tempfile
import unittest

from src.framework_strategies.sglang import SglangStrategy, _arch_to_snake

from tests.helpers import commit, init_repo, tag, write


CONFIG = '''"""Translate DeepSeek V4.1 configs."""


def normalize_deepseek_v41_config(values):
    values = dict(values)
    if values.get("architectures") == ["DeepseekV41ForCausalLM"]:
        values["architectures"] = ["DeepseekV4ForCausalLM"]
    return values
'''

MODEL = """
class DeepseekV4ForCausalLM:
    pass


EntryClass = [DeepseekV4ForCausalLM]
"""


class SglangRemapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = init_repo(self.tmp.name)
        self.strategy = SglangStrategy()
        self.ctx = self.strategy.make_context(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_arch_remap_resolves_target_model(self):
        write(
            self.repo,
            "python/sglang/srt/configs/deepseek_v41.py",
            CONFIG,
        )
        write(
            self.repo,
            "python/sglang/srt/models/deepseek_v4.py",
            MODEL,
        )
        commit(self.repo, "add DeepSeek V4.1 config remap")

        supported, path = self.strategy.check_support(
            "DeepseekV41ForCausalLM", self.ctx
        )

        self.assertTrue(supported)
        self.assertEqual(path, "python/sglang/srt/models/deepseek_v4.py")
        self.assertEqual(self.strategy.remap_info["from"], "DeepseekV41ForCausalLM")
        self.assertEqual(self.strategy.remap_info["to"], "DeepseekV4ForCausalLM")
        self.assertEqual(
            self.strategy.remap_info["file"],
            "python/sglang/srt/configs/deepseek_v41.py",
        )

    def test_unknown_arch_still_returns_false(self):
        write(
            self.repo,
            "python/sglang/srt/configs/deepseek_v41.py",
            CONFIG,
        )
        write(
            self.repo,
            "python/sglang/srt/models/deepseek_v4.py",
            MODEL,
        )
        commit(self.repo, "add DeepSeek V4.1 config remap")

        supported, path = self.strategy.check_support("NoSuchForCausalLM", self.ctx)

        self.assertFalse(supported)
        self.assertIsNone(path)
        self.assertIsNone(self.strategy.remap_info)

    def test_arch_to_snake_for_config_guess(self):
        self.assertEqual(_arch_to_snake("DeepseekV41ForCausalLM"), "deepseek_v41")

    def test_remap_version_uses_config_file_not_base_model(self):
        # The base V4 model existed months before the V4.1 remap; the version
        # must come from the remap config, not deepseek_v4.py's first commit.
        write(
            self.repo,
            "python/sglang/srt/models/deepseek_v4.py",
            MODEL,
        )
        commit(self.repo, "add base DeepSeek V4", date="2026-05-07T00:00:00+00:00")
        tag(self.repo, "v0.5.12", date="2026-05-10T00:00:00+00:00")

        write(
            self.repo,
            "python/sglang/srt/configs/deepseek_v41.py",
            CONFIG,
        )
        commit(self.repo, "add DeepSeek V4.1 remap", date="2026-09-18T00:00:00+00:00")
        tag(self.repo, "v0.5.21", date="2026-09-30T00:00:00+00:00")

        supported, path = self.strategy.check_support(
            "DeepseekV41ForCausalLM", self.ctx
        )
        self.assertTrue(supported)
        self.assertEqual(
            self.strategy.version_path(path),
            "python/sglang/srt/configs/deepseek_v41.py",
        )
        self.assertEqual(
            self.strategy.get_version(self.strategy.version_path(path), self.ctx),
            "v0.5.21",
        )


if __name__ == "__main__":
    unittest.main()
