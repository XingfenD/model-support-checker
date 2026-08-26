"""vLLM-Ascend __init__.py parsing for registered models.

vLLM-Ascend uses ModelRegistry.register_model() calls in __init__.py
to register model architectures, unlike vLLM which uses a dict-based registry.
"""

import os
import re
from typing import Optional

from ...context import Context
from ...http_utils import _get

_INIT_PATH = "vllm_ascend/models/__init__.py"

_BROWSER_UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch_vllm_ascend_registry(ctx: Context, ref: Optional[str] = None, verbose: bool = False) -> str:
    """Fetch vLLM-Ascend models/__init__.py source.

    In local mode (ctx.is_local) the file is read from disk; otherwise
    it is fetched from the GitHub raw CDN.
    """
    if ctx.is_local:
        p = os.path.join(ctx.local_dir, _INIT_PATH)
        if verbose:
            print(f"  [registry] reading local {p}")
        try:
            with open(p, encoding="utf-8") as f:
                body = f.read()
        except OSError:
            raise RuntimeError(f"Could not read local __init__.py at {p}")
        if not body:
            raise RuntimeError(f"Empty local __init__.py at {p}")
        return body

    ref = ref or ctx.branch
    url = f"https://raw.githubusercontent.com/{ctx.repo}/{ref}/{_INIT_PATH}"
    if verbose:
        print(f"  [registry] fetching {url}")
    body, _ = _get(url, ua=_BROWSER_UA)
    if not body:
        raise RuntimeError(f"Could not fetch __init__.py from {url}")
    return body


def parse_vllm_ascend_registry(source: str, verbose: bool = False):
    """Parse __init__.py source and extract registered models.

    Looks for ModelRegistry.register_model() calls and extracts:
    - arch_name: the architecture name (first argument)
    - class_path: the module:class path (second argument)

    Returns:
        registered: dict[arch_name] = class_path
    """
    # Match: ModelRegistry.register_model("ArchName", "module.path:ClassName")
    # Handles multi-line calls with various whitespace
    pattern = re.compile(
        r'ModelRegistry\.register_model\s*\(\s*'
        r'["\'](\w+)["\']\s*,\s*'
        r'["\']([^"\']+)["\']',
        re.MULTILINE
    )

    registered = {}
    for m in pattern.finditer(source):
        arch_name = m.group(1)
        class_path = m.group(2)
        registered[arch_name] = class_path

    if verbose and registered:
        print(f"  [registry] found {len(registered)} registered models")

    return registered


def check_vllm_ascend_registry(arch: str, registered: dict) -> dict:
    """Check an architecture against parsed vLLM-Ascend registry data.

    Returns a dict with status details.
    """
    if arch in registered:
        class_path = registered[arch]
        # Parse "module.path:ClassName" format
        if ":" in class_path:
            module_path, class_name = class_path.rsplit(":", 1)
        else:
            module_path = class_path
            class_name = class_path.split(".")[-1]

        return {
            "status": "supported",
            "module": module_path,
            "class_name": class_name,
        }

    return {"status": "unsupported"}
