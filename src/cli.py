#!/usr/bin/env python3
"""Check whether a HuggingFace / ModelScope model is supported by SGLang or vLLM,
and since which version.

This module is the CLI entry point. The actual work is split across focused
modules: architecture (step 1), docs (step 2), source_check (step 3),
version (step 4), and vllm_registry (vLLM-specific). See each module for the
methodology details.

Usage:
  GITHUB_TOKEN=xxx python3 main.py --framework sglang Qwen/Qwen3.6-35B-A3B
  GITHUB_TOKEN=xxx python3 main.py --framework vllm deepseek-ai/DeepSeek-V3
  python3 main.py --framework vllm meta-llama/Llama-3.1-8B   # best-effort
"""

import argparse
import os
import sys

from . import config
from .architecture import get_architecture
from .docs import check_docs
from .source_check import check_github
from .version import get_version
from .vllm_registry import (
    check_vllm_registry,
    fetch_vllm_registry,
    parse_vllm_registry,
)


def main():
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
    ap.add_argument("--vllm-path", default=None,
                    help="local vllm repo checkout path (skip GitHub API)")
    ap.add_argument("--sglang-path", default=None,
                    help="local sglang repo checkout path (skip GitHub API)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    # Step 1 (framework-independent): architecture name.
    archs, src = get_architecture(args.model_id, args.source)
    arch = archs[0]
    print(f"Model: {args.model_id}")
    print(f"[1] Architecture(s): {', '.join(archs)}  (source: {src})\n")

    frameworks = list(config.FRAMEWORKS) if args.framework == "both" else [args.framework]
    results = {}

    for fw_name in frameworks:
        local_path = args.sglang_path if fw_name == "sglang" else args.vllm_path
        config.set_active(fw_name, local_path)

        print(f"========== {config.NAME} ==========")
        if config.LOCAL_DIR:
            print(f"  (using local checkout: {config.LOCAL_DIR})")

        # Step 3 (authoritative)
        print("[3] GitHub source check (authoritative)...")
        supported, file_path = check_github(arch, args.token, args.verbose)
        print(f"    Supported in source: {'YES' if supported else 'NO'}"
              + (f"  ({file_path})" if file_path else ""))

        # vLLM: parse registry.py for detailed info
        vllm_registry_info = None
        if fw_name == "vllm":
            try:
                ref = args.vllm_ref or config.FRAMEWORKS["vllm"]["branch"]
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
            print(f"[4] Determining first supporting {config.NAME} version...")
            # For vLLM, prefer registry.py path for version detection
            version_path = file_path
            if fw_name == "vllm":
                version_path = file_path or f"{config.MODELS_DIR}/registry.py"
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
        label = config.FRAMEWORKS[fw_name]["label"]
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
