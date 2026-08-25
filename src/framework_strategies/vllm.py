"""vLLM strategy: registry.py parsing, version path, summary formatting."""

from ..vllm_registry import (
    check_vllm_registry,
    fetch_vllm_registry,
    parse_vllm_registry,
)
from .base import FrameworkStrategy


class VllmStrategy(FrameworkStrategy):
    name = "vllm"
    label = "vLLM"
    repo = "vllm-project/vllm"
    branch = "main"
    models_dir = "vllm/model_executor/models"
    docs_url = "https://docs.vllm.ai/en/stable/models/supported_models/"

    def extra_checks(self, arch, token, verbose, ref=None):
        try:
            reg_source = fetch_vllm_registry(ref=ref or self.branch, verbose=verbose)
            reg_supported, reg_previously, reg_oot = parse_vllm_registry(
                reg_source, verbose=verbose
            )
            print(f"    Registry parsed: {len(reg_supported)} architectures registered")
            info = check_vllm_registry(arch, reg_supported, reg_previously, reg_oot)
            status = info["status"]
            if status == "supported":
                print(f"    Category  : {info['category']}")
                print(f"    Module    : {info['module']}")
                print(f"    Class     : {info['class_name']}")
            elif status == "previously_supported":
                print(f"    PREVIOUSLY SUPPORTED (removed)")
                print(f"    Last version: v{info['last_version']}")
            elif status == "oot_plugin":
                print(f"    OUT-OF-TREE PLUGIN REQUIRED")
                print(f"    Plugin: {info['plugin_url']}")
            return info
        except RuntimeError as e:
            if verbose:
                print(f"    [registry] skipped: {e}")
            return None

    def version_path(self, file_path):
        return file_path or f"{self.models_dir}/registry.py"

    def format_summary_extra(self, info):
        if not info:
            return
        status = info["status"]
        if status == "previously_supported":
            print(f"         NOTE: removed after v{info['last_version']}")
        elif status == "oot_plugin":
            print(f"         NOTE: requires plugin {info['plugin_url']}")
        elif status == "supported":
            print(f"         Category: {info['category']}")
