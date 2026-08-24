"""vLLM registry.py source-level parsing (category, module, class, etc.)."""

import os
import re

from . import config
from .http_utils import _get


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
        r'''["'](\w+)["']\s*:\s*\(\s*["']([^"']+)["']\s*,\s*["']([^"']+)["']\s*\)'''
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


def fetch_vllm_registry(ref=None, verbose=False):
    """Fetch vLLM registry.py source.

    In local mode (config.LOCAL_DIR set) the file is read from disk; otherwise
    it is fetched from the GitHub raw CDN. `ref` is ignored in local mode.
    """
    if config.LOCAL_DIR:
        p = os.path.join(config.LOCAL_DIR, config._VLLM_REGISTRY_PATH)
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

    ref = ref or config.FRAMEWORKS["vllm"]["branch"]
    repo = config.FRAMEWORKS["vllm"]["repo"]
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{config._VLLM_REGISTRY_PATH}"
    if verbose:
        print(f"  [registry] fetching {url}")
    body, _ = _get(url, ua=config.BROWSER_UA)
    if not body:
        raise RuntimeError(f"Could not fetch registry.py from {url}")
    return body


def parse_vllm_registry(source, verbose=False):
    """Parse registry.py source and return structured info.

    Returns:
        supported: dict[arch] -> {category, module, class_name}
        previously: dict[arch] -> version_str
        oot: dict[arch] -> plugin_url
    """
    supported = {}
    for dict_name, category in config._VLLM_CATEGORY_MAP.items():
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
