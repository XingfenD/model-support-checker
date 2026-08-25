"""vLLM strategy: registry.py parsing, version path, summary formatting."""

from typing import Optional, Tuple

from ...check import check_support as _check_support
from ...context import Context
from .registry import (
    check_vllm_registry,
    fetch_vllm_registry,
    parse_vllm_registry,
)
from ..base import FrameworkStrategy


class VllmStrategy(FrameworkStrategy):
    name = "vllm"
    label = "vLLM"
    repo = "vllm-project/vllm"
    branch = "main"
    models_dir = "vllm/model_executor/models"
    docs_url = "https://docs.vllm.ai/en/stable/models/supported_models/"

    def check_support(
        self, arch: str, ctx: Context, token: Optional[str] = None, verbose: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Check support via source check (same as base)."""
        return _check_support(arch, ctx, token, verbose)

    def extra_checks(self, arch: str, ctx: Context, token: Optional[str], verbose: bool, ref: Optional[str] = None):
        """Parse registry.py for detailed vLLM model info."""
        try:
            reg_source = fetch_vllm_registry(ctx=ctx, ref=ref or self.branch, verbose=verbose)
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

    def version_path(self, file_path: Optional[str]) -> Optional[str]:
        """Prefer registry.py for version detection if no file found."""
        return file_path or f"{self.models_dir}/registry.py"

    def format_summary_extra(self, info) -> None:
        if not info:
            return
        status = info["status"]
        if status == "previously_supported":
            print(f"         NOTE: removed after v{info['last_version']}")
        elif status == "oot_plugin":
            print(f"         NOTE: requires plugin {info['plugin_url']}")
        elif status == "supported":
            print(f"         Category: {info['category']}")
