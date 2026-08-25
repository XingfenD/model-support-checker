#!/usr/bin/env python3
"""Check whether a HuggingFace / ModelScope model is supported by SGLang or vLLM,
and since which version.

This module is the CLI entry point. The actual work is split across focused
modules: architecture (step 1), docs (step 2), source_check (step 3),
version (step 4), and vllm_registry (vLLM-specific). See each module for the
methodology details.

Usage:
  python3 main.py --setup local                 # first run: clone vLLM+SGLang into .state/repos/ (recommended)
  python3 main.py --setup token                 # first run: use GitHub API (GITHUB_TOKEN per run)
  GITHUB_TOKEN=xxx python3 main.py --framework sglang Qwen/Qwen3.6-35B-A3B
  python3 main.py --framework vllm deepseek-ai/DeepSeek-V3   # after setup
"""

import argparse
import os
import sys
import time

from . import config, state
from .architecture import get_architecture
from .framework_strategies import STRATEGIES
from .source_check import check_github
from .version import get_version

# Max seconds to wait for background checkout refreshes before exiting.
_REFRESH_JOIN_SECONDS = 15


def main():
    ap = argparse.ArgumentParser(description="Check SGLang/vLLM model support.")
    ap.add_argument("model_id", nargs="?", help="e.g. Qwen/Qwen3.6-35B-A3B")
    ap.add_argument("--framework", choices=["sglang", "vllm", "both"], default="both",
                    help="which framework to check (default: both)")
    ap.add_argument("--source", choices=["auto", "hf", "modelscope"],
                    default="auto", help="where to read config.json")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                    help="GitHub token (or set GITHUB_TOKEN env)")
    ap.add_argument("--no-docs", action="store_true", help="skip docs check")
    ap.add_argument("--vllm-ref", default=None,
                    help="vLLM git ref (branch/tag) for registry check (default: main)")
    ap.add_argument("--vllm-path", default=None,
                    help="local vllm repo checkout path (skip GitHub API)")
    ap.add_argument("--sglang-path", default=None,
                    help="local sglang repo checkout path (skip GitHub API)")
    ap.add_argument("--setup", choices=["local", "token"], default=None,
                    help="first-run setup: 'local' clones vLLM+SGLang (recommended), "
                         "'token' uses the GitHub API. Saved to .state/state.json.")
    ap.add_argument("--reset-state", action="store_true",
                    help="forget saved setup state")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.reset_state:
        state.reset()
        if not args.setup:
            return
    if args.setup:
        state.ensure_setup(args.setup, args)
        return

    # Resolve setup state: first run asks the user (TTY menu) or tells the
    # caller to run --setup.
    st = state.load()
    if st is None:
        if sys.stdin.isatty():
            state.ensure_setup(state.first_run_menu(), args)
            st = state.load()
        else:
            raise RuntimeError(
                "First run: no setup found (.state/state.json missing). Ask the "
                "user to choose, then run one of:\n"
                "  python3 main.py --setup local                 # recommended\n"
                "  python3 main.py --setup local --vllm-path P1 --sglang-path P2\n"
                "  python3 main.py --setup token                 # needs GITHUB_TOKEN"
            )
    if st["mode"] == "token" and not args.token and not os.environ.get("GITHUB_TOKEN"):
        print("NOTE: token mode but no GITHUB_TOKEN; results are best-effort.\n")

    vllm_path = args.vllm_path or st.get("vllm_path")
    sglang_path = args.sglang_path or st.get("sglang_path")

    if not args.model_id:
        ap.error("model_id is required (e.g. Qwen/Qwen3.6-35B-A3B)")

    frameworks = list(STRATEGIES) if args.framework == "both" else [args.framework]

    # Local mode: refresh checkouts in the background while checking runs;
    # failures/staleness are only reported at the very end, never blocking.
    local_paths = {}
    for fw_name in frameworks:
        lp = sglang_path if fw_name == "sglang" else vllm_path
        if lp and os.path.isdir(os.path.join(lp, ".git")):
            local_paths[fw_name] = lp
    freshness, refresh_threads = state.start_refresh(local_paths)

    # Step 1 (framework-independent): architecture name.
    archs, src = get_architecture(args.model_id, args.source)
    arch = archs[0]
    print(f"Model: {args.model_id}")
    print(f"[1] Architecture(s): {', '.join(archs)}  (source: {src})\n")

    results = {}

    for fw_name in frameworks:
        local_path = sglang_path if fw_name == "sglang" else vllm_path
        strategy = STRATEGIES[fw_name]
        strategy.activate(local_path)

        print(f"========== {config.NAME} ==========")
        if config.LOCAL_DIR:
            print(f"  (using local checkout: {config.LOCAL_DIR})")

        # Step 3 (authoritative)
        print("[3] GitHub source check (authoritative)...")
        supported, file_path = check_github(arch, args.token, args.verbose)
        print(f"    Supported in source: {'YES' if supported else 'NO'}"
              + (f"  ({file_path})" if file_path else ""))

        # Framework-specific extra checks (e.g. vLLM registry)
        extra = strategy.extra_checks(arch, args.token, args.verbose, ref=args.vllm_ref)

        # Step 2 (docs, supplementary)
        docs = "skipped"
        if not args.no_docs:
            print("[2] Official docs check...")
            docs = strategy.check_docs(arch, args.verbose)
            print(f"    Docs mention: {docs}")

        # Step 4 (version)
        version = None
        if supported:
            print(f"[4] Determining first supporting {config.NAME} version...")
            version = get_version(strategy.version_path(file_path), args.token, args.verbose)
            print(f"    First version: {version}")
        else:
            print("[4] Skipped (not found in source).")

        results[fw_name] = (supported, file_path, version, docs, extra, strategy)
        print()

    # Final combined summary.
    print("=== Summary ===")
    print(f"  Model        : {args.model_id}")
    print(f"  Architecture : {arch}")
    for fw_name in frameworks:
        supported, file_path, version, docs, extra, strategy = results[fw_name]
        line = f"  {strategy.label:6} supported : {'YES' if supported else 'NO'}"
        if supported:
            line += f"  | since {version} | {file_path}"
        print(line)
        strategy.format_summary_extra(extra)
    print("\nNote: GitHub source is the authoritative signal for both frameworks.")
    print("The 'since version' is approximated from the implementation file's first")
    print("commit date and may be off by a release or two; it needs GITHUB_TOKEN")
    print("on rate-limited IPs.")

    _print_refresh_notes(freshness, refresh_threads, args.verbose)


def _print_refresh_notes(freshness, threads, verbose=False):
    """Report background checkout refresh results after the main flow.

    Waits at most _REFRESH_JOIN_SECONDS total so a slow fetch never blocks
    the exit for long; unfinished workers are simply not reported.
    """
    deadline = time.monotonic() + _REFRESH_JOIN_SECONDS
    for t in threads:
        t.join(timeout=max(0.0, deadline - time.monotonic()))
    notes = []
    for fw_name, info in sorted(freshness.items()):
        label = STRATEGIES[fw_name].label
        if "error" in info:
            notes.append(f"{label}: checkout refresh failed ({info['error']}); "
                         f"results reflect the checkout as-is.")
        elif info.get("behind"):
            notes.append(f"{label}: checkout is {info['behind']} commit(s) behind "
                         f"its upstream — update with: git -C {info['path']} pull")
        elif verbose and not info.get("no_upstream"):
            notes.append(f"{label}: checkout is up to date.")
    if notes:
        print("\n=== Checkout freshness ===")
        for n in notes:
            print(f"  NOTE: {n}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
