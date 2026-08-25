"""Interactive setup and first-run menu."""

import os
import sys

from ..framework_strategies import STRATEGIES
from .clone import clone, validate_checkout, get_clone_url, get_default_clone_path
from .constants import REPOS_DIR, STATE_FILE
from .persistence import save


def print_tradeoffs():
    """Print the tradeoffs between local clone and GitHub PAT modes."""
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
    print_tradeoffs()
    while True:
        choice = input("Choose [1/2] (default 1): ").strip()
        if choice in ("", "1"):
            return "local"
        if choice == "2":
            return "token"
        print("Please enter 1 or 2.")


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
            vllm_path = clone(get_clone_url("vllm"), get_default_clone_path("vllm"))
        if not sglang_path:
            sglang_path = clone(get_clone_url("sglang"), get_default_clone_path("sglang"))
        st["vllm_path"] = os.path.abspath(os.path.expanduser(vllm_path))
        st["sglang_path"] = os.path.abspath(os.path.expanduser(sglang_path))
        validate_checkout(st["vllm_path"], "vllm")
        validate_checkout(st["sglang_path"], "sglang")
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
