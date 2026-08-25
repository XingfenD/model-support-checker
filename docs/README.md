# model-support-checker

Check whether a HuggingFace / ModelScope model is supported by **SGLang** or
**vLLM**, and since which version.

## Setup (one-time)

The tool is **stateful**: your access mode is persisted in `.state/state.json`
(gitignored), so later runs need no flags or tokens.

On first run you choose between two access modes — **local clone is recommended**:

| | Local clone (recommended) | GitHub PAT |
|---|---|---|
| Result quality | Definitive (files grepped on disk) | Best-effort without token; code search 403s anonymously |
| Rate limits | None | Yes — can break batch/version checks |
| Repeat checks | Fast (disk reads) | Slower (GitHub API) |
| Works offline | Yes, after initial clone | No |
| Cost | ~1 GB+ disk (vLLM full history needed) | None |
| Freshness | Stale until `git pull` | Always current |

```bash
python3 main.py --setup local                                  # clone vLLM+SGLang into .state/repos/
python3 main.py --setup local --vllm-path P1 --sglang-path P2  # reuse existing checkouts
python3 main.py --setup token                                  # GitHub API mode

python3 main.py --reset-state   # forget setup (cloned repos are kept and reused)
```

Notes:

- Local clones are full clones (`--depth 1` breaks version detection).
- The GitHub token is NEVER written to `.state/`; in token mode export
  `GITHUB_TOKEN` per run.
- Re-run `--setup <mode>` anytime to switch modes; explicit `--vllm-path` /
  `--sglang-path` / `--token` flags override the saved state for that run.
- Each run in local mode refreshes checkouts in the background (`git fetch`)
  and reports staleness or failures at the end — never blocking the main
  check.

## Methodology

For each framework the checker runs four framework-agnostic steps:

1. **Architecture name** — read `architectures` from the model's `config.json`
   (HuggingFace first, ModelScope API as fallback).
2. **Official docs** (supplementary) — grep the framework's supported-models page.
3. **GitHub source** (authoritative) — search the framework's models directory on
   GitHub. Both SGLang and vLLM register a model by mapping the HF architecture
   string to a class in `<models_dir>/<file>.py`, so the architecture string is
   always present in its implementation file.
   - For vLLM this step additionally parses `registry.py` to extract the model
     category, module path, class name, and checks
     `_PREVIOUSLY_SUPPORTED_MODELS` / `_OOT_SUPPORTED_MODELS`.
4. **Version** — determine the first framework release that contains the
   implementation (via the file's earliest commit date → nearest release).

The authoritative "is it supported" check uses the GitHub **code-search API**
with a path filter on the models directory. Anonymous code search returns 403,
so a `GITHUB_TOKEN` is required for a definitive answer. Without a token the
tool falls back to scraping the models directory tree + grepping candidate files
on the raw CDN; that fallback can be incomplete, so a NO without a token is not
definitive. Step 4 also needs a token on rate-limited IPs.

### Local checkouts (no GitHub API)

Local mode is the recommended setup (`--setup local` clones both repos into
`.state/repos/` automatically). All source reads (models directory,
`registry.py`, and version history) are served from disk via `git`, and **no
GitHub API requests are made** — only the architecture lookup (step 1) and the
docs check (step 2) still touch the network.

```bash
# Override saved paths for a single run (no GITHUB_TOKEN needed for source/registry/version)
python3 main.py --framework vllm   --vllm-path   /path/to/vllm   deepseek-ai/DeepSeek-V3
python3 main.py --framework sglang --sglang-path /path/to/sglang Qwen/Qwen3.6-35B-A3B
```

`--vllm-ref` is ignored when `--vllm-path` is given. The local path must be a
git checkout of the framework repo (so `git log`/`git tag` are available for
version detection). Keep checkouts fresh with an occasional `git pull`.

No third-party dependencies — standard library only.

## Usage

```bash
# After setup, just pass a model id
python3 main.py --framework sglang Qwen/Qwen3.6-35B-A3B
python3 main.py --framework vllm deepseek-ai/DeepSeek-V3

# Check both frameworks at once (default)
python3 main.py meta-llama/Llama-3.1-8B

# Token mode: GITHUB_TOKEN per run (never stored)
GITHUB_TOKEN=xxx python3 main.py meta-llama/Llama-3.1-8B
```

### Options

| Flag            | Description                                                        |
| --------------- | ------------------------------------------------------------------ |
| `model_id`      | HuggingFace or ModelScope model id (positional; required except with `--setup`/`--reset-state`). |
| `--setup`       | One-time setup: `local` (clone repos into `.state/repos/`, recommended) or `token`; persists to `.state/state.json`. |
| `--reset-state` | Forget saved setup state (cloned repos kept).                      |
| `--framework`   | `sglang`, `vllm`, or `both` (default: `both`).                     |
| `--source`      | `auto`, `hf`, or `modelscope` for reading `config.json`.           |
| `--token`       | GitHub token (or set `GITHUB_TOKEN` env); overrides saved state for this run. |
| `--no-docs`     | Skip the docs check.                                               |
| `--vllm-ref`    | vLLM git ref (branch/tag) for the registry check (default: `main`).|
| `--vllm-path`   | Local vllm repo checkout; overrides saved path for this run.       |
| `--sglang-path` | Local sglang repo checkout; overrides saved path for this run.     |
| `-v, --verbose` | Verbose output.                                                    |

## License

[The Unlicense](../LICENSE) — released into the public domain.
