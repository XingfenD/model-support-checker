#!/usr/bin/env python3
"""Entry point for model-support-checker.

Usage:
  GITHUB_TOKEN=xxx python3 main.py --framework sglang Qwen/Qwen3.6-35B-A3B
  GITHUB_TOKEN=xxx python3 main.py --framework vllm deepseek-ai/DeepSeek-V3
  python3 main.py --framework vllm meta-llama/Llama-3.1-8B   # best-effort
"""

import sys

from src.cli import main

if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
