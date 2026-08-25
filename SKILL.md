---
name: model-support-checker
description: Use when checking HuggingFace or ModelScope model support for SGLang or vLLM, finding the first supporting version, or diagnosing "model not supported" errors.
---

# Model Support Checker

## Overview

Check whether a HuggingFace / ModelScope model is supported by **SGLang** or **vLLM**, and since which version. The checker runs four framework-agnostic steps and uses GitHub source as the authoritative signal.

The tool is **stateful**: the access mode chosen during one-time setup is persisted in `.state/state.json` (gitignored), so later runs need no flags or tokens.

## When to Use

- Before deploying a model, to confirm SGLang/vLLM compatibility.
- When a model fails to load and you suspect it is not yet implemented.
- When comparing framework coverage for a new model release.
- When you need to know the minimum required SGLang/vLLM version.

## First Run Setup (REQUIRED once)

If `.state/state.json` does not exist yet, **ask the user** which access mode they want BEFORE any model check. Present both options with this comparison and **recommend the local clone**:

| | Local clone (recommended) | GitHub PAT |
|---|---|---|
| Result quality | Definitive (files grepped on disk) | Best-effort without token; code search 403s anonymously |
| Rate limits | None | Yes — can break batch/version checks |
| Repeat checks | Fast (disk reads) | Slower (GitHub API) |
| Works offline | Yes, after initial clone | No |
| Cost | ~1 GB+ disk (vLLM full history needed) | None |
| Freshness | Stale until `git pull` | Always current |

Then run exactly one of:

```bash
python3 main.py --setup local                                  # clone vLLM+SGLang into .state/repos/
python3 main.py --setup local --vllm-path P1 --sglang-path P2  # reuse existing checkouts
python3 main.py --setup token                                  # GitHub API mode
```

Notes:

- Local clones are full clones (`--depth 1` breaks version detection).
- The GitHub token is NEVER written to `.state/`; in token mode export `GITHUB_TOKEN` per run.
- Re-run `--setup <mode>` anytime to switch modes; `--reset-state` forgets it (cloned repos are kept and reused).
- Each run in local mode refreshes checkouts in the background (`git fetch`) and reports staleness or failures at the end — never blocking the main check.

## Methodology

1. **Architecture** — read `architectures` from the model's `config.json` (HuggingFace first, ModelScope fallback).
2. **Docs** (supplementary) — grep the framework's supported-models page.
3. **GitHub source** (authoritative) — search the framework's models directory for the architecture string.
   - For vLLM, also parse `registry.py` for category, module, class, and check `_PREVIOUSLY_SUPPORTED_MODELS` / `_OOT_SUPPORTED_MODELS`.
4. **Version** — find the first release containing the implementation file (earliest commit → nearest release).

## Quick Reference

| Task | Command |
|------|---------|
| First-run setup (local, recommended) | `python3 main.py --setup local` |
| First-run setup (GitHub PAT) | `python3 main.py --setup token` |
| Check both frameworks (after setup) | `python3 main.py meta-llama/Llama-3.1-8B` |
| Check one framework | `python3 main.py --framework vllm deepseek-ai/DeepSeek-V3` |
| Override saved paths for one run | `python3 main.py --vllm-path /p --sglang-path /q <model>` |
| Switch mode / reconfigure | `python3 main.py --setup local` or `--setup token` |
| Forget setup state | `python3 main.py --reset-state` |
| Skip docs check | `python3 main.py --no-docs <model_id>` |
| Verbose output | `python3 main.py -v <model_id>` |

## Important Flags

| Flag | Description |
|------|-------------|
| `model_id` | HuggingFace or ModelScope model id (positional; required except with `--setup`/`--reset-state`) |
| `--setup` | `local` (clone repos into `.state/repos/`, recommended) or `token` (GitHub API); persists to `.state/state.json` |
| `--reset-state` | Delete saved state (cloned repos kept) |
| `--framework` | `sglang`, `vllm`, or `both` (default: `both`) |
| `--source` | `auto`, `hf`, or `modelscope` for reading `config.json` |
| `--token` | GitHub token (or set `GITHUB_TOKEN` env; overrides saved mode paths only in that run) |
| `--no-docs` | Skip the docs check |
| `--vllm-ref` | vLLM git ref for registry check (default: `main`; ignored in local mode) |
| `--vllm-path` | Local vLLM checkout; overrides the saved path for this run |
| `--sglang-path` | Local SGLang checkout; overrides the saved path for this run |
| `-v, --verbose` | Verbose output |

## Common Mistakes

- **Checking a model before setup** — without `.state/state.json` the tool refuses to run and prints the `--setup` commands. Ask the user which mode they want first.
- **Token mode without `GITHUB_TOKEN`** — code search returns 403 for anonymous requests, so a "NO" result is best-effort and not definitive. Prefer local mode.
- **Using a shallow git clone for local mode** — version detection needs full git history; use `--setup local` so it clones correctly.
- **Stale local checkouts** — each run refreshes in the background and prints a note at the end if the checkout is behind; pull when warned.
- **Expecting exact version numbers** — the "since version" is approximated from the file's earliest commit and may be off by one release.
- **Forgetting `--no-docs`** when docs pages are JS-rendered or unreachable.

## Notes

- No third-party dependencies; uses Python standard library only.
- License: The Unlicense.
