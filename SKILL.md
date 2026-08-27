---
name: model-support-checker
description: Use when checking HuggingFace or ModelScope model support for SGLang, vLLM, or vLLM-Ascend, finding the first supporting version, or diagnosing "model not supported" errors.
---

# Model Support Checker

Check whether a HuggingFace / ModelScope model is supported by **SGLang**, **vLLM**, or **vLLM-Ascend**, and since which version.

## Methodology

The authoritative signal: does the framework's **source code** contain an implementation for the model's architecture string? Docs are supplementary.

1. **Architecture** — `architectures` from `config.json` (HF → ModelScope fallback). Override with `--arch`.
2. **Docs** (supplementary) — grep the framework's supported-models page.
3. **Source** (authoritative) — search the models directory for the architecture string.
4. **Reconcile** — if docs say YES but source says NO, manually inspect the framework's repo to resolve the discrepancy (see Step 4b).
5. **Version** — earliest commit on the implementation file → nearest release tag.

The tool is stateful; mode persists in `.state/state.json`. Local clone (recommended) greps on disk. Token mode uses GitHub API.

## Skill Workflow

**Step 1 — Doctor.** `python3 main.py --doctor`. `[ERROR]` → fix first, stop. `[WARN]` → ignore, continue.

**Step 2 — Setup (optional).** Only if no state exists. Recommend local: `python3 main.py --setup local`.

**Step 3 — Resolve model ID.** Infer full `<org>/<model_name>` from user input, matching the hosting platform convention. Parse URLs or short names. Query the web if uncertain.

**Step 4 — Run.**
```bash
python3 main.py [--framework <fw>] [--source <src>] [--arch <arch>] <model_id>
```
- All frameworks: `python3 main.py <model_id>`
- One framework: `python3 main.py --framework vllm <model_id>`
- Manual arch (no config.json needed): `python3 main.py --arch LlamaForCausalLM`
- Arch + model: `python3 main.py --framework vllm --arch DeepseekV3ForCausalLM <model_id>`

**Step 4b — Reconcile discrepancies.** If docs=YES but source=NO for any framework, manually inspect the repo:
1. Read the framework's registry file (vLLM: `registry.py`; vLLM-Ascend: `__init__.py`) to check if the architecture is registered.
2. If registered, trace the module path to find the implementation file (may be in a new directory structure like `vllm/models/<family>/`).
3. Verify the architecture string exists in that file.
4. Update the result to YES with the correct file path.

**Step 5 — Report.** Parse Summary. Report: YES/NO per framework, minimum version, file path, vLLM category/module/class.

## Fallback Strategies

### Fallback 1: config.json fetch fails

Escalate in order:

1. **Switch platform** — retry with `--source hf` (default is modelscope).
2. **webfetch** — agent fetches `config.json` directly:
   - HF: `https://huggingface.co/<org>/<model>/resolve/main/config.json`
   - MS: `https://modelscope.cn/models/<org>/<model>/resolve/master/config.json`
   Extract `architectures`, then: `python3 main.py --arch <ArchName> <model_id>`
3. **Guide user** — if webfetch fails (private/gated), provide links for the user to read `architectures` from `config.json`:
   - HF: `https://huggingface.co/<org>/<model>/blob/main/config.json`
   - MS: `https://modelscope.cn/models/<org>/<model>/files`
   Then run with `--arch`.

### Fallback 2: Script cannot run

Bypass the script; follow methodology manually:

1. Get architecture (webfetch or ask user).
2. Search framework GitHub repos for the architecture string:
   - vLLM (`vllm-project/vllm`): `vllm/model_executor/models/` or `vllm/models/<family>/`
   - SGLang (`sgl-project/sglang`): `python/sglang/srt/models/`
   - vLLM-Ascend (`vllm-project/vllm-ascend`): `vllm_ascend/models/` (may include subdirs like `minimax_m3/`)
3. Check official supported-models docs.
4. Earliest commit → nearest release tag for version.
5. Report in script Summary format.

## Quick Reference

| Flag | Description |
|------|-------------|
| `--framework` | `sglang` / `vllm` / `vllm-ascend` / `all` |
| `--source` | `auto` / `hf` / `modelscope` |
| `--arch` | Manual arch name(s); skips config.json |
| `--doctor` | Check setup state |
| `--setup` | `local` or `token` |

`python3 main.py --help` for full flag list.

## Common Mistakes

- **Skipping doctor** — always `--doctor` first.
- **Giving up on config.json failure** — escalate: switch platform → webfetch → guide user.
- **Not using `--arch`** — when config.json is unreachable, pass `--arch` instead of aborting.
- **Trusting source=NO when docs=YES** — frameworks may reorganize directories; do Step 4b reconciliation.
