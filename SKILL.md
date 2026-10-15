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
6. **Deploy** — once support is confirmed, read the official deployment docs and hand the user a ready-to-run serving command (see Step 6).

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

**Step 4b — Reconcile discrepancies.** If docs=YES but source=NO for any framework, the directory layout has likely changed. Do not assume known paths; instead:
1. Read the framework's registry file to find where the architecture is registered.
2. Extract the module path from the registry entry.
3. Trace that module path to locate the actual implementation file on disk.
4. Verify the architecture string exists in that file.
5. If the registry does not contain the architecture, search the entire framework repo for the architecture string (e.g. `rg <ArchName> <repo_root>`) to locate where it is referenced.
6. Update the result to YES with the correct file path.

**Step 5 — Report.** Parse Summary. Report: YES/NO per framework, minimum version, file path, vLLM category/module/class.

**Step 6 — Deployment advice.** After confirming support, do NOT stop at "YES" — the user's real goal is to run the model. Read the official deployment docs and hand over a ready-to-run command:

1. **Fetch official serving docs, in this authority order:**
   - Framework tutorial page — vLLM-Ascend: `https://docs.vllm.ai/projects/ascend/<lang>/latest/tutorials/models/<Model>.html`; vLLM recipes: `recipes.vllm.ai`; SGLang cookbook: `cookbook.sglang.io`. These carry vendor-tuned flags the model card may lack.
   - Model card README (HF + ModelScope) — "Deploy / Serve locally" section.
   - Quantized variant docs if the user runs one (W8A8 / MXFP8 / AWQ often have DIFFERENT required flags, e.g. `--quantization ascend` for W8A8 on vLLM-Ascend).
2. **Output the launch command verbatim from the docs** (do not assemble flags from memory), plus: hardware/memory requirement, required env vars, and a verification command (log follow + a smoke completion request).
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

### Fallback 3: Source=NO but model is recent / may ship support out-of-tree

The script's source check is authoritative for the **merged `main` branch checkout**, but framework teams frequently ship support through channels that are NOT in the default `main` checkout the script greps:

- **Official Docker images** with the implementation baked in (e.g. `lmsysorg/sglang:glm-5.3-flash`, `vllm/vllm-openai-rocm:glm53-flash`).
- **A separate support branch** not yet merged to main (e.g. `xinyuan/glm-5.3-flash-support`).
- **Vendor recipes / cookbook pages** (e.g. `recipes.vllm.ai/<org>/<model>`, `cookbook.sglang.io/...`).

This is the reverse of Step 4b (docs=YES, source=NO). When source=NO, do NOT report a flat "unsupported" until the official deployment docs are checked:

1. Fetch the model card on **both** HF and ModelScope (one is often gated/401):
   - HF: `https://huggingface.co/<org>/<model>` and `.../resolve/main/README.md`
   - MS: `https://modelscope.cn/models/<org>/<model>` and `.../resolve/master/README.md`
2. Find a "Deploy / Serve locally" section. If it lists vLLM / SGLang / vLLM-Ascend, the model IS deployable — capture the exact mechanism:
   - Docker image tag(s) and required version (e.g. "vLLM 0.29.0+", "use docker before integration is in the public repo").
   - Extra requirements: FlashInfer version, GPU arch (Hopper+/Blackwell/gfx950), `--tool-call-parser` / `--reasoning-parser`, MTP/speculative config.
   - Caveats: features only on a specific branch/PR, image alone insufficient, etc.
3. Follow the recipe links to get the concrete launch command and image name.
4. Report a **nuanced** result instead of a bare NO. Distinguish these states:
   - `merged` — in the public repo/PyPI, version-known.
   - `image-only` — runs via vendor Docker image, not yet in public main.
   - `branch-only` — needs a specific git branch/PR checkout.
   - `unsupported` — no official path at all.

The official model card + recipes are authoritative about HOW to run, even when the implementation is not in the default `main` checkout. This supersedes a flat NO from the script.

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
- **Trusting source=NO as final for recent models** — vendors often ship support via official Docker images / separate branches / recipe pages that are NOT in the default `main` checkout the script greps. Check the official model card + recipes (Fallback 3) before concluding "unsupported".
- **Stopping at "YES" without deployment advice** — the user asked because they want to RUN the model. Always finish with Step 6: official launch command + hardware requirement.
