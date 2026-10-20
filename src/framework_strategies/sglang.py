"""SGLang strategy."""

import ast
import re
from typing import Optional, Tuple

from ..context import Context
from .base import FrameworkStrategy

_CONFIGS_DIR = "python/sglang/srt/configs"


class SglangStrategy(FrameworkStrategy):
    name = "sglang"
    label = "SGLang"
    repo = "sgl-project/sglang"
    branch = "main"
    models_dir = "python/sglang/srt/models"
    docs_url = "https://docs.sglang.io/docs/supported-models"

    def __init__(self):
        super().__init__()
        self.remap_info = None

    def check_support(
        self, arch: str, ctx: Context, token: Optional[str] = None,
        verbose: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        self.remap_info = None
        supported, file_path = super().check_support(arch, ctx, token, verbose)
        if supported:
            return True, file_path

        # SGLang may normalize an HF architecture name to an internal one in
        # ``configs/`` before dispatching (DeepSeek V4.1 is the canonical case).
        remap = self._find_arch_remap(arch, ctx, verbose)
        if not remap:
            return False, None
        target, config_file = remap
        supported, file_path = super().check_support(target, ctx, token, verbose)
        if not supported:
            return False, None
        self.remap_info = {"from": arch, "to": target, "file": config_file}
        if verbose:
            print(f"    [config-remap] {arch} -> {target} ({config_file})")
        return True, file_path

    def _find_arch_remap(self, arch: str, ctx: Context, verbose: bool = False):
        files = sorted(self.list_py_files(ctx, _CONFIGS_DIR, verbose))
        # If the directory listing is unavailable (anonymous rate limit), try
        # the conventional config name derived from the architecture.
        guess = f"{_arch_to_snake(arch)}.py"
        if guess not in files:
            files.append(guess)
        for fname in files:
            rel = f"{_CONFIGS_DIR}/{fname}"
            body = ctx.read_source(rel)
            if not body or arch not in body:
                continue
            target = _target_arch_from_source(body, arch)
            if target and target != arch:
                return target, rel
        return None

    def format_summary_extra(self, info) -> None:
        if self.remap_info:
            print(
                f"         Mapped: {self.remap_info['from']} -> "
                f"{self.remap_info['to']} ({self.remap_info['file']})"
            )

    def version_path(self, file_path):
        """For a remapped architecture, the remap config is the support signal.

        The target model file may predate the remap by months (e.g.
        ``deepseek_v4.py`` vs ``configs/deepseek_v41.py``), which would report
        the base model's first release instead of the variant's.
        """
        if self.remap_info:
            return self.remap_info["file"]
        return file_path


def _target_arch_from_source(source: str, arch: str) -> Optional[str]:
    """Return the architecture a config module rewrites *arch* into."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _target_arch_from_source_regex(source, arch)

    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if not _test_mentions_arch(node.test, arch):
            continue
        target = _assigned_arch_in_nodes(node.body)
        if target and target != arch:
            return target
    return _target_arch_from_source_regex(source, arch)


def _test_mentions_arch(test: ast.AST, arch: str) -> bool:
    has_arch = any(
        isinstance(n, ast.Constant) and n.value == arch for n in ast.walk(test)
    )
    return has_arch and "architectures" in ast.dump(test)


def _assigned_arch_in_nodes(nodes) -> Optional[str]:
    for stmt in nodes:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Assign):
                continue
            if not any(_is_architectures_target(t) for t in node.targets):
                continue
            target = _arch_from_value(node.value)
            if target:
                return target
    return None


def _is_architectures_target(target: ast.AST) -> bool:
    if isinstance(target, ast.Subscript):
        sl = target.slice
        return isinstance(sl, ast.Constant) and sl.value == "architectures"
    if isinstance(target, ast.Attribute):
        return target.attr == "architectures"
    return False


def _arch_from_value(value: ast.AST) -> Optional[str]:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, (ast.List, ast.Tuple)):
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                return elt.value
    return None


def _target_arch_from_source_regex(source: str, arch: str) -> Optional[str]:
    pattern = re.compile(
        r"architectures[^\n]*==\s*\[\s*['\"]" + re.escape(arch) +
        r"['\"]\s*\][^\n]*:[\s\S]{0,200}?"
        r"architectures[^\n]*=\s*\[\s*['\"]([A-Za-z0-9_]+)['\"]",
    )
    m = pattern.search(source)
    return m.group(1) if m else None


def _arch_to_snake(arch: str) -> str:
    name = arch[:-len("ForCausalLM")] if arch.endswith("ForCausalLM") else arch
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
