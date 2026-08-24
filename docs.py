"""Step 2: best-effort check of the framework's official docs."""

import re

import config
from http_utils import _get


def check_docs(arch, verbose=False):
    body, _ = _get(config.DOCS_URL)
    if not body:
        if verbose:
            print(f"  [docs] could not fetch {config.DOCS_URL} (may be JS-rendered).")
        return "unknown"
    if arch in body or arch.lower() in body.lower():
        return "yes"
    family = re.split(r"(?=[A-Z])", arch)[0].lower()
    if family and family in body.lower():
        return "maybe"
    return "no"
