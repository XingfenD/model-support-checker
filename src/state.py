"""Persistent setup state for model-support-checker.

State lives in <skill root>/.state/ (gitignored via .gitignore) so the
first-run choice (GitHub PAT vs local clone) survives across runs without
being tracked by git. The GitHub token itself is NEVER stored here.
"""

import json
import os
import subprocess
import sys
import threading

from . import config
from .framework_strategies import STRATEGIES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(ROOT, ".state")
REPOS_DIR = os.path.join(STATE_DIR, "repos")
STATE_FILE = os.path.join(STATE_DIR, "state.json")


def load():
    """Return the saved state dict, or None if not set up yet."""
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) and st.get("mode") else None
    except (OSError, ValueError):
        return None


def save(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)
    return st


def reset():
    """Forget setup state. Cloned repos under .state/repos/ are kept and will
    be reused automatically by a later `--setup local`."""
    try:
        os.remove(STATE_FILE)
        print(f"Removed {STATE_FILE} (cloned repos kept at {REPOS_DIR}).")
    except FileNotFoundError:
        print("No saved state found.")


def _print_tradeoffs():
    print(
        "First-run setup: choose how to access vLLM/SGLang sources.\n"
        "\n"
        "  1) Local clone  (recommended)\n"
        "     + definitive results: files grepped on disk, no rate limits\n"
        "     + fast repeat checks; version detection from full git history\n"
        "     + works offline after the initial clone\n"
        "     - one-time download (vLLM full history ~1 GB+, SGLang smaller)\n"
        "     - needs occasional 'git pull' or answers go stale\n"
        "\n"
        "  2) GitHub PAT\n"
        "     + no disk usage; always reflects remote main\n"
        "     - code search 403s without a token; anonymous results are\n"
        "       best-effort only\n"
        "     - API rate limits can break batch/version checks\n"
        "     - GITHUB_TOKEN must be provided every run (never stored here)"
    )


def first_run_menu():
    """Interactive TTY menu. Returns the chosen mode ('local' | 'token')."""
    _print_tradeoffs()
    while True:
        choice = input("Choose [1/2] (default 1): ").strip()
        if choice in ("", "1"):
            return "local"
        if choice == "2":
            return "token"
        print("Please enter 1 or 2.")


def _clone(url, target):
    """Clone url into target (full history -- shallow clones break step 4)."""
    if os.path.isdir(os.path.join(target, ".git")):
        print(f"  reusing existing clone: {target}")
        return target
    os.makedirs(os.path.dirname(target), exist_ok=True)
    print(f"  cloning {url} -> {target} (full history, may take a while)...")
    r = subprocess.run(["git", "clone", url, target])
    if r.returncode != 0:
        raise RuntimeError(f"git clone failed for {url}")
    return target


def _validate_checkout(path, fw_name):
    strategy = STRATEGIES[fw_name]
    if not os.path.isfile(os.path.join(path, strategy.models_dir, "__init__.py")):
        print(
            f"  WARNING: {strategy.models_dir} not found under {path}; "
            f"is this really a {strategy.label} checkout?"
        )


def ensure_setup(mode, args):
    """Create and persist setup state. Returns the new state dict."""
    st = {"mode": mode}
    if mode == "local":
        vllm_path = args.vllm_path
        sglang_path = args.sglang_path
        if sys.stdin.isatty():
            if not vllm_path:
                raw = input(
                    f"vLLM checkout path [Enter = clone into {REPOS_DIR}/vllm]: "
                ).strip()
                vllm_path = raw or None
            if not sglang_path:
                raw = input(
                    f"SGLang checkout path [Enter = clone into {REPOS_DIR}/sglang]: "
                ).strip()
                sglang_path = raw or None
        if not vllm_path:
            vllm_path = _clone(
                f"https://github.com/{STRATEGIES['vllm'].repo}",
                os.path.join(REPOS_DIR, "vllm"),
            )
        if not sglang_path:
            sglang_path = _clone(
                f"https://github.com/{STRATEGIES['sglang'].repo}",
                os.path.join(REPOS_DIR, "sglang"),
            )
        st["vllm_path"] = os.path.abspath(os.path.expanduser(vllm_path))
        st["sglang_path"] = os.path.abspath(os.path.expanduser(sglang_path))
        _validate_checkout(st["vllm_path"], "vllm")
        _validate_checkout(st["sglang_path"], "sglang")
    elif mode == "token":
        if not args.token and not os.environ.get("GITHUB_TOKEN"):
            print(
                "NOTE: no GITHUB_TOKEN set. Code search needs it; export "
                "GITHUB_TOKEN per run (it is never stored in .state/)."
            )
    else:
        raise RuntimeError(f"Unknown setup mode: {mode}")

    save(st)
    print(f"Setup saved ({mode}) -> {STATE_FILE}")
    return st


def fetch_status(path, result, key):
    """Background worker: `git fetch` a local checkout and count how far
    behind its upstream it is. Writes into result[key]; NEVER raises — any
    failure is recorded as {"error": ...} so the main flow is never blocked."""
    info = {"path": path}
    try:
        remotes = subprocess.run(
            ["git", "-C", path, "remote"],
            capture_output=True, text=True,
        ).stdout.strip()
        if not remotes:
            info["no_upstream"] = True
            result[key] = info
            return
        f = subprocess.run(
            ["git", "-C", path, "fetch", "--quiet", "origin"],
            capture_output=True, text=True, timeout=300,
        )
        if f.returncode != 0:
            lines = [ln for ln in f.stderr.strip().splitlines() if ln.strip()]
            info["error"] = lines[-1] if lines else "git fetch failed"
        else:
            up = subprocess.run(
                ["git", "-C", path, "rev-parse", "--abbrev-ref",
                 "--symbolic-full-name", "@{upstream}"],
                capture_output=True, text=True,
            )
            head = subprocess.run(
                ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            if up.returncode != 0 or head in ("", "HEAD"):
                info["no_upstream"] = True
            else:
                cnt = subprocess.run(
                    ["git", "-C", path, "rev-list", "--count",
                     f"HEAD..{up.stdout.strip()}"],
                    capture_output=True, text=True,
                )
                if cnt.returncode == 0 and cnt.stdout.strip().isdigit():
                    info["behind"] = int(cnt.stdout.strip())
                else:
                    info["no_upstream"] = True
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        # ponytail: broad catch is the point — refresh must never be fatal
        info["error"] = str(e)
    result[key] = info


def start_refresh(framework_paths):
    """Spawn daemon threads to refresh local checkouts concurrently.

    Returns (results_dict, threads); results are filled in as workers finish.
    """
    results = {}
    threads = []
    for key, path in framework_paths.items():
        t = threading.Thread(target=fetch_status, args=(path, results, key),
                             daemon=True)
        t.start()
        threads.append(t)
    return results, threads
