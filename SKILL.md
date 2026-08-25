---
name: model-support-checker
description: Use when checking HuggingFace or ModelScope model support for SGLang or vLLM, finding the first supporting version, or diagnosing "model not supported" errors.
---

# Model Support Checker

## Overview

Check whether a HuggingFace / ModelScope model is supported by **SGLang** or **vLLM**, and since which version. The checker runs four framework-agnostic steps and uses GitHub source as the authoritative signal.

## When to Use

- Before deploying a model, to confirm SGLang/vLLM compatibility.
- When a model fails to load and you suspect it is not yet implemented.
- When comparing framework coverage for a new model release.
- When you need to know the minimum required SGLang/vLLM version.

## Methodology

1. **Architecture** — read `architectures` from the model's `config.json` (HuggingFace first, ModelScope fallback).
2. **Docs** (supplementary) — grep the framework's supported-models page.
3. **GitHub source** (authoritative) — search the framework's models directory for the architecture string.
   - For vLLM, also parse `registry.py` for category, module, class, and check `_PREVIOUSLY_SUPPORTED_MODELS` / `_OOT_SUPPORTED_MODELS`.
4. **Version** — find the first release containing the implementation file (earliest commit → nearest release).

## Quick Reference

| Task | Command |
|------|---------|
| Check both frameworks | `GITHUB_TOKEN=xxx python3 main.py meta-llama/Llama-3.1-8B` |
| Check one framework | `python3 main.py --framework vllm deepseek-ai/DeepSeek-V3` |
| Use local checkouts (no GitHub API) | `python3 main.py --vllm-path /path/to/vllm --sglang-path /path/to/sglang Qwen/Qwen3.6-35B-A3B` |
| Skip docs check | `python3 main.py --no-docs <model_id>` |
| Verbose output | `python3 main.py -v <model_id>` |

## Important Flags

| Flag | Description |
|------|-------------|
| `model_id` | HuggingFace or ModelScope model id (positional, required) |
| `--framework` | `sglang`, `vllm`, or `both` (default: `both`) |
| `--source` | `auto`, `hf`, or `modelscope` for reading `config.json` |
| `--token` | GitHub token (or set `GITHUB_TOKEN` env) |
| `--no-docs` | Skip the docs check |
| `--vllm-ref` | vLLM git ref for registry check (default: `main`) |
| `--vllm-path` | Local vLLM checkout; skips GitHub API for source |
| `--sglang-path` | Local SGLang checkout; skips GitHub API for source |
| `-v, --verbose` | Verbose output |

## Common Mistakes

- **Running without `GITHUB_TOKEN`** — code search returns 403 for anonymous requests, so a "NO" result is best-effort and not definitive.
- **Expecting exact version numbers** — the "since version" is approximated from the file's earliest commit and may be off by one release.
- **Using a shallow git clone for local mode** — version detection needs full git history.
- **Forgetting `--no-docs`** when docs pages are JS-rendered or unreachable.

## Notes

- No third-party dependencies; uses Python standard library only.
- License: The Unlicense.
