"""Step 3: GitHub source check (the authoritative support signal)."""

import os
import re
import urllib.parse

from . import config
from .http_utils import _get, _get_json


def _list_model_files(verbose=False):
    """List every .py file in the framework's models directory.

    Local mode (config.LOCAL_DIR set): read the directory straight from disk.
    Network mode:
      Primary: the REST Contents API (returns the FULL directory reliably, even
      for large dirs) -- needs a token or a non-rate-limited IP.
      Fallback: scrape the GitHub tree web page (website CDN, no token, but can
      be paginated/incomplete for very large directories).
    """
    # Local checkout: list files from disk.
    if config.LOCAL_DIR:
        d = os.path.join(config.LOCAL_DIR, config.MODELS_DIR)
        try:
            names = {f for f in os.listdir(d) if f.endswith(".py")}
        except OSError:
            if verbose:
                print(f"  [local] could not list models directory {d}.")
            return None
        names.discard("__init__.py")
        if names:
            if verbose:
                print(f"  [local] listed {len(names)} model files from {d}.")
            return names
        return None

    # 1) Contents API (full, reliable).
    url = f"{config.API}/contents/{config.MODELS_DIR}"
    data = _get_json(url)
    if data:
        names = {
            e["name"]
            for e in data
            if e.get("type") == "file" and e["name"].endswith(".py")
        }
        names.discard("__init__.py")
        if names:
            if verbose:
                print(f"  [github] listed {len(names)} model files via Contents API.")
            return names

    # 2) Tree web page (best-effort fallback).
    if verbose:
        print("  [github] Contents API unavailable; scraping tree page.")
    turl = (
        f"https://github.com/{config.REPO}/tree/"
        f"{config.FRAMEWORKS[config.NAME.lower()]['branch']}/{config.MODELS_DIR}"
    )
    try:
        body, _ = _get(turl, ua=config.BROWSER_UA)
    except RuntimeError:
        body = None
    if not body:
        if verbose:
            print("  [github] could not fetch models directory listing.")
        return None
    names = set(re.findall(r'"name":"([a-zA-Z0-9_]+\.py)"', body))
    names.discard("__init__.py")
    return names


def _match_files(arch, files):
    """Pick candidate model files that may implement the architecture.

    A file is a candidate if, after dropping underscores:
      - its stem is a prefix of the architecture, or vice versa, OR
      - it shares the architecture's leading "family" word
        (e.g. DeepseekV3ForCausalLM is implemented in deepseek_v2.py, which
        also registers DeepseekV2ForCausalLM via a multi-class registration).
    """
    a = arch.lower().replace("_", "")
    fam = re.match(r"[A-Za-z]+", arch)  # leading alphabetic word, e.g. "Deepseek"
    fam = fam.group(0).lower() if fam else ""
    out = []
    for f in files:
        if not f.endswith(".py"):
            continue
        stem = f[:-3].lower().replace("_", "")
        if (
            a.startswith(stem)
            or stem.startswith(a)
            or (fam and (stem.startswith(fam) or fam.startswith(stem)))
        ):
            out.append(f)
    # Shortest stem first; we grep every candidate anyway.
    return sorted(out, key=len)


def check_github(arch, token, verbose=False):
    """Return (supported: bool, file_path: str|None).

    Primary (authoritative): the code-search API with a path filter on the
    models directory. Needs GITHUB_TOKEN (anonymous code search returns 403)
    and correctly handles files that register several architectures at once.

    Fallback (token-less, best-effort): scrape the models directory tree from
    the GitHub website and grep candidate files on the raw CDN. The website tree
    can be paginated/incomplete, so a NO here is not definitive without a token.

    Local mode (config.LOCAL_DIR set): no GitHub API is called; the model files
    are grepped directly on disk and a hit is definitive.
    """
    if config.LOCAL_DIR:
        return _check_local(arch, verbose)

    if token:
        inner = "^" + config.MODELS_DIR.replace("/", r"\/") + r"\/"
        q = f"{arch} repo:{config.REPO} path:/{inner}/"
        url = f"{config.API}/search/code?q={urllib.parse.quote(q)}&per_page=20"
        data = _get_json(url, token)
        if data:
            for item in data.get("items", []):
                if item["path"].startswith(config.MODELS_DIR) and item["path"].endswith(".py"):
                    if verbose:
                        print(f"  [github] code-search hit: {item['path']}")
                    return True, item["path"]
        elif verbose:
            print("  [github] code search returned nothing / was rate-limited.")

    # Fallback: scrape the directory tree + raw grep (no token).
    if not token and verbose:
        print("  [github] no token: using best-effort tree scrape "
              "(may be incomplete; set GITHUB_TOKEN for a definitive answer).")
    files = _list_model_files(verbose)
    candidates = _match_files(arch, files) if files else []
    if verbose:
        print("  [github] fallback candidates: " + ", ".join(candidates) or "(none)")
    for fname in candidates:
        path = f"{config.MODELS_DIR}/{fname}"
        body = config.read_source(path)
        if body and arch in body:
            if verbose:
                print(f"  [github] '{arch}' found in {path}")
            return True, path
    return False, None


def _check_local(arch, verbose=False):
    """Local-only implementation of check_github: grep model files on disk."""
    files = _list_model_files(verbose)
    candidates = _match_files(arch, files) if files else []
    if verbose:
        print("  [local] candidates: " + (", ".join(candidates) or "(none)"))
    for fname in candidates:
        path = f"{config.MODELS_DIR}/{fname}"
        body = config.read_source(path)
        if body and arch in body:
            if verbose:
                print(f"  [local] '{arch}' found in {path}")
            return True, path
    return False, None
