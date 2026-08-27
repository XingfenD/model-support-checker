"""vLLM strategy: registry.py parsing, version path, summary formatting."""

import os
from typing import Optional, Tuple

from ...check import check_support as _check_support
from ...context import Context
from .registry import (
    check_vllm_registry,
    fetch_vllm_registry,
    parse_vllm_registry,
)
from ..base import FrameworkStrategy

_NEW_MODELS_DIR = "vllm/models"


class VllmStrategy(FrameworkStrategy):
    name = "vllm"
    label = "vLLM"
    repo = "vllm-project/vllm"
    branch = "main"
    models_dir = "vllm/model_executor/models"
    docs_url = "https://docs.vllm.ai/en/stable/models/supported_models/"

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
            reg_source = fetch_vllm_registry(ctx=ctx, ref=self.branch, verbose=verbose)
            reg_supported, _, _ = parse_vllm_registry(reg_source, verbose=verbose)
        except RuntimeError as e:
            if verbose:
                print(f"    [registry-fallback] skipped: {e}")
            return False, None
        if arch not in reg_supported:
            return False, None
        module = reg_supported[arch]["module"]
        if not module.startswith("vllm.models."):
            return False, None
        resolved = self._resolve_new_style_path(module, arch, ctx, verbose)
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
        """Prefer registry-resolved path, then file_path, then registry.py."""
        return self._registry_file_path or file_path or f"{self.models_dir}/registry.py"

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
