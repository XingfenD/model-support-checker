"""vLLM-Ascend strategy: __init__.py parsing for registered models."""

from typing import Optional, Tuple

from ...check import check_support as _check_support
from ...context import Context
from .registry import (
    check_vllm_ascend_registry,
    fetch_vllm_ascend_registry,
    parse_vllm_ascend_registry,
)
from ..base import FrameworkStrategy


class VllmAscendStrategy(FrameworkStrategy):
    name = "vllm-ascend"
    label = "vLLM-Ascend"
    repo = "vllm-project/vllm-ascend"
    branch = "main"
    models_dir = "vllm_ascend/models"
    docs_url = "https://docs.vllm.ai/projects/ascend/en/latest/"

    def check_support(
        self, arch: str, ctx: Context, token: Optional[str] = None, verbose: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Check support via source check (same as base)."""
        return _check_support(arch, ctx, token, verbose)

    def extra_checks(self, arch: str, ctx: Context, token: Optional[str], verbose: bool, ref: Optional[str] = None):
        """Parse __init__.py for registered model info."""
        try:
            init_source = fetch_vllm_ascend_registry(ctx=ctx, ref=ref or self.branch, verbose=verbose)
            registered = parse_vllm_ascend_registry(init_source, verbose=verbose)
            print(f"    Registry parsed: {len(registered)} architectures registered")
            info = check_vllm_ascend_registry(arch, registered)
            status = info["status"]
            if status == "supported":
                print(f"    Module    : {info['module']}")
                print(f"    Class     : {info['class_name']}")
            return info
        except RuntimeError as e:
            if verbose:
                print(f"    [registry] skipped: {e}")
            return None

    def version_path(self, file_path: Optional[str]) -> Optional[str]:
        """Prefer __init__.py for version detection if no file found."""
        return file_path or f"{self.models_dir}/__init__.py"

    def format_summary_extra(self, info) -> None:
        if not info:
            return
        status = info["status"]
        if status == "supported":
            print(f"         Module: {info['module']}")
