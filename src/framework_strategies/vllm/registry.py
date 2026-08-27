"""vLLM registry.py source-level parsing (category, module, class, etc.)."""

import os
import re
from typing import Optional

from ...context import Context
from ...http_utils import _get

_REGISTRY_PATH = "vllm/model_executor/models/registry.py"

_CATEGORY_MAP = {
    "_TEXT_GENERATION_MODELS": "text_generation",
    "_EMBEDDING_MODELS": "embedding",
    "_LATE_INTERACTION_MODELS": "late_interaction",
    "_REWARD_MODELS": "reward",
    "_TOKEN_CLASSIFICATION_MODELS": "token_classification",
    "_SEQUENCE_CLASSIFICATION_MODELS": "sequence_classification",
    "_MULTIMODAL_MODELS": "multimodal",
    "_SPECULATIVE_DECODING_MODELS": "speculative_decoding",
    "_TRANSFORMERS_SUPPORTED_MODELS": "transformers_supported",
    "_TRANSFORMERS_BACKEND_MODELS": "transformers_backend",
}

_BROWSER_UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _parse_dict_entries(source, dict_name):
    """Extract architecture keys from a Python dict literal in source.

    Returns dict[arch_name] = (module_str, class_str).
    """
    pattern = rf"^{re.escape(dict_name)}\s*=\s*\{{"
    match = re.search(pattern, source, re.MULTILINE)
    if not match:
        return {}

    start = match.end()
    depth = 1
    i = start
    while i < len(source) and depth > 0:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch in ("'", '"'):
            quote = ch
            i += 1
            while i < len(source):
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == quote:
                    break
                i += 1
        i += 1

    body = source[start : i - 1]

    entry_re = re.compile(
        r'''["'](\w+)["']\s*:\s*\(\s*["']([^"']+)["']\s*,\s*["']([^"']+)["']\s*,?\s*\)'''
    )
    result = {}
    for m in entry_re.finditer(body):
        result[m.group(1)] = (m.group(2), m.group(3))
    return result


def _parse_simple_dict(source, dict_name):
    """Extract entries from a simple dict: "Key": "Value"."""
    pattern = rf"^{re.escape(dict_name)}\s*=\s*\{{"
    match = re.search(pattern, source, re.MULTILINE)
    if not match:
        return {}

    start = match.end()
    depth = 1
    i = start
    while i < len(source) and depth > 0:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch in ("'", '"'):
            quote = ch
            i += 1
            while i < len(source):
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == quote:
                    break
                i += 1
        i += 1

    body = source[start : i - 1]

    entry_re = re.compile(r'''["'](\w+)["']\s*:\s*["']([^"']+)["']''')
    result = {}
    for m in entry_re.finditer(body):
        result[m.group(1)] = m.group(2)
    return result


def fetch_vllm_registry(ctx: Context, ref: Optional[str] = None, verbose: bool = False) -> str:
    """Fetch vLLM registry.py source.

    In local mode (ctx.is_local) the file is read from disk; otherwise
    it is fetched from the GitHub raw CDN.
    """
    if ctx.is_local:
        p = os.path.join(ctx.local_dir, _REGISTRY_PATH)
        if verbose:
            print(f"  [registry] reading local {p}")
        try:
            with open(p, encoding="utf-8") as f:
                body = f.read()
        except OSError:
            raise RuntimeError(f"Could not read local registry.py at {p}")
        if not body:
            raise RuntimeError(f"Empty local registry.py at {p}")
        return body

    ref = ref or ctx.branch
    url = f"https://raw.githubusercontent.com/{ctx.repo}/{ref}/{_REGISTRY_PATH}"
    if verbose:
        print(f"  [registry] fetching {url}")
    body, _ = _get(url, ua=_BROWSER_UA)
    if not body:
        raise RuntimeError(f"Could not fetch registry.py from {url}")
    return body


def parse_vllm_registry(source, verbose: bool = False):
    """Parse registry.py source and return structured info.

    Returns:
        supported: dict[arch] -> {category, module, class_name}
        previously: dict[arch] -> version_str
        oot: dict[arch] -> plugin_url
    """
    supported = {}
    for dict_name, category in _CATEGORY_MAP.items():
        entries = _parse_dict_entries(source, dict_name)
        for arch, (mod, cls) in entries.items():
            supported[arch] = {
                "category": category,
                "module": mod,
                "class_name": cls,
            }
        if verbose and entries:
            print(f"  [registry] {dict_name}: {len(entries)} entries")

    previously = _parse_simple_dict(source, "_PREVIOUSLY_SUPPORTED_MODELS")
    if verbose and previously:
        print(f"  [registry] _PREVIOUSLY_SUPPORTED_MODELS: {len(previously)} entries")

    oot = _parse_simple_dict(source, "_OOT_SUPPORTED_MODELS")
    if verbose and oot:
        print(f"  [registry] _OOT_SUPPORTED_MODELS: {len(oot)} entries")

    return supported, previously, oot


def check_vllm_registry(arch, supported, previously, oot):
    """Check an architecture against parsed vLLM registry data.

    Returns a dict with status details.
    """
    if arch in supported:
        info = supported[arch]
        mod = info["module"]
        if mod.startswith("vllm."):
            full_module = mod
        else:
            full_module = f"vllm.model_executor.models.{mod}"
        return {
            "status": "supported",
            "category": info["category"],
            "module": full_module,
            "class_name": info["class_name"],
        }

    if arch in previously:
        return {
            "status": "previously_supported",
            "last_version": previously[arch],
        }

    if arch in oot:
        return {
            "status": "oot_plugin",
            "plugin_url": oot[arch],
        }

    return {"status": "unsupported"}
