"""Regression tests for vLLM-Ascend registry parsing.

``vllm_ascend/models/__init__.py`` registers most architectures through a
dict literal (``_CUSTOMIZED_MODEL_ARCHS``) that is iterated into
``ModelRegistry.register_model()``.  Parsing only the direct call form misses
``DeepseekV41ForCausalLM`` and produces a false NO.
"""

import tempfile
import unittest

from src.framework_strategies.vllm_ascend import (
    VllmAscendStrategy,
    parse_vllm_ascend_registry,
)

from tests.helpers import commit, init_repo, write


REGISTRY = '''"""Model registrations."""

_CUSTOMIZED_MODEL_ARCHS = {
    "DeepseekV41ForCausalLM":
        "vllm_ascend.models.deepseek_v41.vl_model:AscendDeepseekV41ForCausalLM",
    "DeepseekV41DSparkModel":
        "vllm_ascend.models.deepseek_v41.dspark:DSparkDeepseekV41ForCausalLM",
}

for arch_name, model_cls in _CUSTOMIZED_MODEL_ARCHS.items():
    ModelRegistry.register_model(arch_name, model_cls)
'''

MODEL = """
class AscendDeepseekV41ForCausalLM:
    pass
"""


class AscendRegistryTests(unittest.TestCase):
    def test_parse_dict_registry_entries(self):
        registered = parse_vllm_ascend_registry(REGISTRY)

        self.assertIn("DeepseekV41ForCausalLM", registered)
        self.assertEqual(
            registered["DeepseekV41ForCausalLM"],
            "vllm_ascend.models.deepseek_v41.vl_model:"
            "AscendDeepseekV41ForCausalLM",
        )

    def test_parse_register_model_calls_still_works(self):
        source = (
            'ModelRegistry.register_model(\n'
            '    "LegacyForCausalLM",\n'
            '    "vllm_ascend.models.legacy:LegacyForCausalLM",\n'
            ')\n'
        )
        registered = parse_vllm_ascend_registry(source)

        self.assertEqual(
            registered["LegacyForCausalLM"],
            "vllm_ascend.models.legacy:LegacyForCausalLM",
        )

    def test_check_support_resolves_dict_registered_module(self):
        with tempfile.TemporaryDirectory() as repo:
            init_repo(repo)
            write(repo, "vllm_ascend/models/__init__.py", REGISTRY)
            write(
                repo,
                "vllm_ascend/models/deepseek_v41/__init__.py",
                "",
            )
            write(
                repo,
                "vllm_ascend/models/deepseek_v41/vl_model.py",
                MODEL,
            )
            commit(repo, "add DeepSeek V4.1 Ascend wrapper")

            strategy = VllmAscendStrategy()
            ctx = strategy.make_context(repo)
            supported, path = strategy.check_support(
                "DeepseekV41ForCausalLM", ctx
            )

            self.assertTrue(supported)
            self.assertEqual(
                path,
                "vllm_ascend/models/deepseek_v41/vl_model.py",
            )


if __name__ == "__main__":
    unittest.main()
