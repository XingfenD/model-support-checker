#!/usr/bin/env python3
"""Entry point for model-support-checker.

Usage:
  python3 main.py --setup local                 # first run (recommended)
  python3 main.py --doctor                      # check setup state
  GITHUB_TOKEN=xxx python3 main.py --framework sglang Qwen/Qwen3.6-35B-A3B
  python3 main.py --framework vllm deepseek-ai/DeepSeek-V3   # after setup
  python3 main.py --framework vllm-ascend deepseek-ai/DeepSeek-V3
"""

import sys

from src.cli import main

if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
