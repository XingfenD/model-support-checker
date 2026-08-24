#!/usr/bin/env python3
"""Check whether a HuggingFace / ModelScope model is supported by SGLang or vLLM,
and since which version.

Methodology (four steps), framework-agnostic:
  1. Get the architecture name from the model's config.json
     (HuggingFace first, ModelScope API as fallback).
  2. Cross-check the official docs (framework-specific supported-models page).
  3. Search the framework source on GitHub (the authoritative check).
     Both SGLang and vLLM register a model by mapping the HF architecture
     string to a class in <models_dir>/<file>.py, so the architecture string is
     always present in its implementation file.
     For vLLM, this step additionally parses ``registry.py`` to extract the
     model category, module path, class name, and checks
     ``_PREVIOUSLY_SUPPORTED_MODELS`` / ``_OOT_SUPPORTED_MODELS``.
  4. Determine the first framework release that contains the implementation
     (via the file's earliest commit date -> nearest release).

The authoritative "is it supported" check uses the GitHub *code-search API*
with a path filter on the models directory -- this is exactly the
`repo:<org>/<repo> path:/^<models_dir>// <arch>` query and it REQUIRES
GITHUB_TOKEN (anonymous code search returns 403). It correctly handles files
that register several architectures at once. Without a token we fall back to
scraping the models directory tree from the GitHub website + grepping candidate
files on the raw CDN; that fallback can be paginated/incomplete, so a NO without
a token is not definitive. Step 4 (version) also uses the GitHub API and needs a
token on rate-limited IPs.

No third-party dependencies: standard library only.

Usage:
  GITHUB_TOKEN=xxx python3 model_support_check.py --framework sglang Qwen/Qwen3.6-35B-A3B
  GITHUB_TOKEN=xxx python3 model_support_check.py --framework vllm deepseek-ai/DeepSeek-V3
  python3 model_support_check.py --framework vllm meta-llama/Llama-3.1-8B   # best-effort
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

FRAMEWORKS = {
    "sglang": {
        "label": "SGLang",
        "repo": "sgl-project/sglang",
        "branch": "main",
        "models_dir": "python/sglang/srt/models",
        "docs": "https://docs.sglang.io/docs/supported-models",
    },
    "vllm": {
        "label": "vLLM",
        "repo": "vllm-project/vllm",
        "branch": "main",
        "models_dir": "vllm/model_executor/models",
        "docs": "https://docs.vllm.ai/en/stable/models/supported_models/",
    },
}

# Module-level globals, set from FRAMEWORKS in main().
REPO = None
API = None
RAW = None
MODELS_DIR = None
DOCS_URL = None
NAME = None  # human label, e.g. "SGLang"

UA = {"User-Agent": "model-support-check/1.0"}
BROWSER_UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# vLLM registry.py dictionary names -> human-readable category labels.
_VLLM_REGISTRY_PATH = "vllm/model_executor/models/registry.py"
_VLLM_CATEGORY_MAP = {
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


def _get(url, headers=None, timeout=25, ua=None):
    h = dict(ua or UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), r.headers
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise RuntimeError(f"GitHub rate limit / forbidden ({e.code})")
        if e.code == 404:
            return None, e.headers
        raise


def _get_json(url, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        body, _ = _get(url, headers)
    except RuntimeError:
        return None
    if body is None:
        return None
    return json.loads(body)


# ---------------------------------------------------------------------------
# Step 1: architecture name
# ---------------------------------------------------------------------------
def get_architecture(model_id, source="auto"):
    """Return (architectures: list[str], source_used: str)."""
    if source in ("auto", "hf"):
        url = f"https://huggingface.co/{model_id}/resolve/main/config.json"
        body, _ = _get(url)
        if body:
            try:
                data = json.loads(body)
                if data.get("architectures"):
                    return data["architectures"], "huggingface"
            except json.JSONDecodeError:
                pass

    if source in ("auto", "modelscope"):
        url = f"https://modelscope.cn/models/{model_id}/resolve/master/config.json"
        body, _ = _get(url)
        if body:
            try:
                data = json.loads(body)
                if data.get("architectures"):
                    return data["architectures"], "modelscope"
            except json.JSONDecodeError:
                pass
        api = f"https://modelscope.cn/api/v1/models/{model_id}"
        data = _get_json(api)
        if data:
            arch = data.get("Architectures") or data.get("architectures")
            if arch:
                return [arch] if isinstance(arch, str) else arch, "modelscope-api"

    raise RuntimeError(
        f"Could not fetch config.json for '{model_id}' from HuggingFace or ModelScope."
    )


# ---------------------------------------------------------------------------
# Step 2: official docs (best-effort)
# ---------------------------------------------------------------------------
def check_docs(arch, verbose=False):
    body, _ = _get(DOCS_URL)
    if not body:
        if verbose:
            print(f"  [docs] could not fetch {DOCS_URL} (may be JS-rendered).")
        return "unknown"
    if arch in body or arch.lower() in body.lower():
        return "yes"
    family = re.split(r"(?=[A-Z])", arch)[0].lower()
    if family and family in body.lower():
        return "maybe"
    return "no"


# ---------------------------------------------------------------------------
# Step 3: GitHub source (authoritative)
# ---------------------------------------------------------------------------
def _list_model_files(verbose=False):
    """List every .py file in the framework's models directory.

    Primary: the REST Contents API (returns the FULL directory reliably, even
    for large dirs) -- needs a token or a non-rate-limited IP.
    Fallback: scrape the GitHub tree web page (website CDN, no token, but can be
    paginated/incomplete for very large directories).
    """
    # 1) Contents API (full, reliable).
    url = f"{API}/contents/{MODELS_DIR}"
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
    turl = f"https://github.com/{REPO}/tree/{FRAMEWORKS[NAME.lower()]['branch']}/{MODELS_DIR}"
    try:
        body, _ = _get(turl, ua=BROWSER_UA)
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


# ---------------------------------------------------------------------------
# vLLM registry.py source-level parsing
# ---------------------------------------------------------------------------
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
    """Fetch vLLM registry.py source from GitHub raw CDN."""
    ref = ref or FRAMEWORKS["vllm"]["branch"]
    repo = FRAMEWORKS["vllm"]["repo"]
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{_VLLM_REGISTRY_PATH}"
    if verbose:
        print(f"  [registry] fetching {url}")
    body, _ = _get(url, ua=BROWSER_UA)
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
    for dict_name, category in _VLLM_CATEGORY_MAP.items():
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


def check_github(arch, token, verbose=False):
    """Return (supported: bool, file_path: str|None).

    Primary (authoritative): the code-search API with a path filter on the
    models directory. Needs GITHUB_TOKEN (anonymous code search returns 403)
    and correctly handles files that register several architectures at once.

    Fallback (token-less, best-effort): scrape the models directory tree from
    the GitHub website and grep candidate files on the raw CDN. The website tree
    can be paginated/incomplete, so a NO here is not definitive without a token.
    """
    if token:
        inner = "^" + MODELS_DIR.replace("/", r"\/") + r"\/"
        q = f"{arch} repo:{REPO} path:/{inner}/"
        url = f"{API}/search/code?q={urllib.parse.quote(q)}&per_page=20"
        data = _get_json(url, token)
        if data:
            for item in data.get("items", []):
                if item["path"].startswith(MODELS_DIR) and item["path"].endswith(".py"):
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
        path = f"{MODELS_DIR}/{fname}"
        try:
            body, _ = _get(f"{RAW}/{path}")
        except RuntimeError:
            body = None
        if body and arch in body:
            if verbose:
                print(f"  [github] '{arch}' found in {path}")
            return True, path
    return False, None


# ---------------------------------------------------------------------------
# Step 4: version
# ---------------------------------------------------------------------------
def _earliest_commit_date(path, token):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{API}/commits?path={urllib.parse.quote(path)}&per_page=1"
    try:
        body, hdrs = _get(url, headers)
    except RuntimeError as e:
        raise RuntimeError(str(e)) from e
    if not body:
        return None
    link = hdrs.get("Link", "")
    last_page = 1
    for part in link.split(","):
        if 'rel="last"' in part:
            m = re.search(r"[?&]page=(\d+)", part)
            if m:
                last_page = int(m.group(1))
    if last_page > 1:
        try:
            body, _ = _get(f"{url}&page={last_page}", headers)
        except RuntimeError:
            body = None
        if not body:
            return None
    commits = json.loads(body)
    if not commits:
        return None
    commit = commits[-1]["commit"]
    return commit.get("committer", {}).get("date") or commit.get("author", {}).get("date")


def _first_release_after(date_iso, token):
    rels = _get_json(f"{API}/releases?per_page=100", token) or []
    picked = None
    for r in rels:
        pub = r.get("published_at")
        if not pub:
            continue
        if pub >= date_iso and (picked is None or pub < picked["published_at"]):
            picked = r
    return picked["tag_name"] if picked else "unreleased (main)"


def get_version(file_path, token, verbose=False):
    if not file_path:
        return None
    try:
        date = _earliest_commit_date(file_path, token)
    except RuntimeError as e:
        return f"unknown ({e}; try GITHUB_TOKEN)"
    if verbose:
        print(f"  [version] earliest commit touching {file_path}: {date}")
    if not date:
        return "unknown"
    try:
        return _first_release_after(date, token)
    except RuntimeError as e:
        return f"unknown ({e}; try GITHUB_TOKEN)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    global REPO, API, RAW, MODELS_DIR, DOCS_URL, NAME
    ap = argparse.ArgumentParser(description="Check SGLang/vLLM model support.")
    ap.add_argument("model_id", help="e.g. Qwen/Qwen3.6-35B-A3B")
    ap.add_argument("--framework", choices=["sglang", "vllm", "both"], default="both",
                    help="which framework to check (default: both)")
    ap.add_argument("--source", choices=["auto", "hf", "modelscope"],
                    default="auto", help="where to read config.json")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                    help="GitHub token (or set GITHUB_TOKEN env)")
    ap.add_argument("--no-docs", action="store_true", help="skip docs check")
    ap.add_argument("--vllm-ref", default=None,
                    help="vLLM git ref (branch/tag) for registry check (default: main)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    # Step 1 (framework-independent): architecture name.
    archs, src = get_architecture(args.model_id, args.source)
    arch = archs[0]
    print(f"Model: {args.model_id}")
    print(f"[1] Architecture(s): {', '.join(archs)}  (source: {src})\n")

    frameworks = list(FRAMEWORKS) if args.framework == "both" else [args.framework]
    results = {}

    for fw_name in frameworks:
        fw = FRAMEWORKS[fw_name]
        NAME = fw["label"]
        REPO = fw["repo"]
        API = f"https://api.github.com/repos/{REPO}"
        RAW = f"https://raw.githubusercontent.com/{REPO}/{fw['branch']}"
        MODELS_DIR = fw["models_dir"]
        DOCS_URL = fw["docs"]

        print(f"========== {NAME} ==========")

        # Step 3 (authoritative)
        print("[3] GitHub source check (authoritative)...")
        supported, file_path = check_github(arch, args.token, args.verbose)
        print(f"    Supported in source: {'YES' if supported else 'NO'}"
              + (f"  ({file_path})" if file_path else ""))

        # vLLM: parse registry.py for detailed info
        vllm_registry_info = None
        if fw_name == "vllm":
            try:
                ref = args.vllm_ref or fw["branch"]
                reg_source = fetch_vllm_registry(ref=ref, verbose=args.verbose)
                reg_supported, reg_previously, reg_oot = parse_vllm_registry(
                    reg_source, verbose=args.verbose
                )
                total = len(reg_supported)
                print(f"    Registry parsed: {total} architectures registered")
                vllm_registry_info = check_vllm_registry(
                    arch, reg_supported, reg_previously, reg_oot
                )
                status = vllm_registry_info["status"]
                if status == "supported":
                    print(f"    Category  : {vllm_registry_info['category']}")
                    print(f"    Module    : {vllm_registry_info['module']}")
                    print(f"    Class     : {vllm_registry_info['class_name']}")
                elif status == "previously_supported":
                    print(f"    PREVIOUSLY SUPPORTED (removed)")
                    print(f"    Last version: v{vllm_registry_info['last_version']}")
                elif status == "oot_plugin":
                    print(f"    OUT-OF-TREE PLUGIN REQUIRED")
                    print(f"    Plugin: {vllm_registry_info['plugin_url']}")
            except RuntimeError as e:
                if args.verbose:
                    print(f"    [registry] skipped: {e}")

        # Step 2 (docs, supplementary)
        docs = "skipped"
        if not args.no_docs:
            print("[2] Official docs check...")
            docs = check_docs(arch, args.verbose)
            print(f"    Docs mention: {docs}")

        # Step 4 (version)
        version = None
        if supported:
            print(f"[4] Determining first supporting {NAME} version...")
            # For vLLM, prefer registry.py path for version detection
            version_path = file_path
            if fw_name == "vllm":
                version_path = file_path or f"{MODELS_DIR}/registry.py"
            version = get_version(version_path, args.token, args.verbose)
            print(f"    First version: {version}")
        else:
            print("[4] Skipped (not found in source).")

        results[fw_name] = (supported, file_path, version, docs, vllm_registry_info)
        print()

    # Final combined summary.
    print("=== Summary ===")
    print(f"  Model        : {args.model_id}")
    print(f"  Architecture : {arch}")
    for fw_name in frameworks:
        supported, file_path, version, docs, vllm_info = results[fw_name]
        label = FRAMEWORKS[fw_name]["label"]
        line = f"  {label:6} supported : {'YES' if supported else 'NO'}"
        if supported:
            line += f"  | since {version} | {file_path}"
        print(line)
        # vLLM: show extra registry info
        if fw_name == "vllm" and vllm_info:
            status = vllm_info["status"]
            if status == "previously_supported":
                print(f"         NOTE: removed after v{vllm_info['last_version']}")
            elif status == "oot_plugin":
                print(f"         NOTE: requires plugin {vllm_info['plugin_url']}")
            elif status == "supported":
                print(f"         Category: {vllm_info['category']}")
    print("\nNote: GitHub source is the authoritative signal for both frameworks.")
    print("The 'since version' is approximated from the implementation file's first")
    print("commit date and may be off by a release or two; it needs GITHUB_TOKEN")
    print("on rate-limited IPs.")

if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
