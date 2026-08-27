"""vLLM-Ascend strategy: __init__.py parsing for registered models."""

import os
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

    def __init__(self):
        super().__init__()
        self._registry_file_path = None

    def check_support(
        self, arch: str, ctx: Context, token: Optional[str] = None, verbose: bool = False
    ) -> Tuple[bool, Optional[str]]:
        supported, file_path = _check_support(arch, ctx, token, verbose)
        if supported:
            return True, file_path
        try:
            init_source = fetch_vllm_ascend_registry(ctx=ctx, ref=self.branch, verbose=verbose)
            registered = parse_vllm_ascend_registry(init_source, verbose=verbose)
        except RuntimeError as e:
            if verbose:
                print(f"    [registry-fallback] skipped: {e}")
            return False, None
        if arch not in registered:
            return False, None
        class_path = registered[arch]
        if ":" in class_path:
            module_path = class_path.rsplit(":", 1)[0]
        else:
            module_path = class_path
        if not module_path.startswith("vllm_ascend.models."):
            return False, None
        resolved = self._resolve_new_style_path(module_path, arch, ctx, verbose)
        if resolved:
            self._registry_file_path = resolved
            if verbose:
                print(f"    [registry-fallback] found via registry: {resolved}")
            return True, resolved
        return False, None

    def _resolve_new_style_path(self, module, arch, ctx, verbose):
        pkg_rel = module.replace(".", os.sep)
        candidates = [
            f"{pkg_rel}/__init__.py",
            f"{pkg_rel}.py",
        ]
        for rel in candidates:
            body = ctx.read_source(rel)
            if body and arch in body:
                return rel
        if ctx.is_local:
            pkg_dir = os.path.join(ctx.local_dir, pkg_rel)
            if os.path.isdir(pkg_dir):
                for fname in sorted(os.listdir(pkg_dir)):
                    if fname.endswith(".py") and fname != "__init__.py":
                        fpath = os.path.join(pkg_dir, fname)
                        try:
                            with open(fpath, encoding="utf-8") as f:
                                body = f.read()
                        except OSError:
                            continue
                        if arch in body:
                            return f"{pkg_rel}/{fname}"
        return None

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
        """Prefer registry-resolved path, then file_path, then __init__.py."""
        return self._registry_file_path or file_path or f"{self.models_dir}/__init__.py"

    def format_summary_extra(self, info) -> None:
        if not info:
            return
        status = info["status"]
        if status == "supported":
            print(f"         Module: {info['module']}")
