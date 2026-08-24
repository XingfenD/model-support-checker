# model-support-checker

Check whether a HuggingFace / ModelScope model is supported by **SGLang** or
**vLLM**, and since which version.

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

No third-party dependencies — standard library only.

## Usage

```bash
# Check a single framework
GITHUB_TOKEN=xxx python3 main.py --framework sglang Qwen/Qwen3.6-35B-A3B
GITHUB_TOKEN=xxx python3 main.py --framework vllm deepseek-ai/DeepSeek-V3

# Check both frameworks at once (default)
GITHUB_TOKEN=xxx python3 main.py --framework both meta-llama/Llama-3.1-8B

# Best-effort, no token (results may be incomplete)
python3 main.py --framework vllm meta-llama/Llama-3.1-8B
```

### Options

| Flag            | Description                                                        |
| --------------- | ------------------------------------------------------------------ |
| `model_id`      | HuggingFace or ModelScope model id (positional, required).         |
| `--framework`   | `sglang`, `vllm`, or `both` (default: `both`).                     |
| `--source`      | `auto`, `hf`, or `modelscope` for reading `config.json`.           |
| `--token`       | GitHub token (or set `GITHUB_TOKEN` env).                          |
| `--no-docs`     | Skip the docs check.                                               |
| `--vllm-ref`    | vLLM git ref (branch/tag) for the registry check (default: `main`).|
| `-v, --verbose` | Verbose output.                                                    |

## License

[The Unlicense](../LICENSE) — released into the public domain.
