"""Framework configuration and active-framework state for model-support-checker."""

import os

FRAMEWORKS = {
    "sglang": {
        "label": "SGLang",
        "repo": "sgl-project/sglang",
        "branch": "main",
        "models_dir": "python/sglang/srt/models",
        "docs": "https://docs.sglang.io/docs/supported-models",
    },
    "vllm": {
        "label": "vLLM",
        "repo": "vllm-project/vllm",
        "branch": "main",
        "models_dir": "vllm/model_executor/models",
        "docs": "https://docs.vllm.ai/en/stable/models/supported_models/",
    },
}

# vLLM registry.py dictionary names -> human-readable category labels.
_VLLM_REGISTRY_PATH = "vllm/model_executor/models/registry.py"
_VLLM_CATEGORY_MAP = {
    "_TEXT_GENERATION_MODELS": "text_generation",
    "_EMBEDDING_MODELS": "embedding",
    "_LATE_INTERACTION_MODELS": "late_interaction",
    "_REWARD_MODELS": "reward",
    "_TOKEN_CLASSIFICATION_MODELS": "token_classification",
    "_SEQUENCE_CLASSIFICATION_MODELS": "sequence_classification",
    "_MULTIMODAL_MODELS": "multimodal",
    "_SPECULATIVE_DECODING_MODELS": "speculative_decoding",
    "_TRANSFORMERS_SUPPORTED_MODELS": "transformers_supported",
    "_TRANSFORMERS_BACKEND_MODELS": "transformers_backend",
}

UA = {"User-Agent": "model-support-check/1.0"}
BROWSER_UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Module-level globals describing the currently active framework, set by
# set_active() from FRAMEWORKS in main(). Referenced dynamically (config.X)
# so updates are visible to every module.
REPO = None
API = None
RAW = None
MODELS_DIR = None
DOCS_URL = None
NAME = None  # human label, e.g. "SGLang"
LOCAL_DIR = None  # local checkout path; when set, no GitHub API calls are made


def set_active(fw_name, local_dir=None):
    """Initialise the active-framework globals from FRAMEWORKS[fw_name].

    If local_dir is provided it is treated as a local checkout of the framework
    repository; all source reads (models dir, registry.py, version history) are
    served from disk via git, and no GitHub API requests are made.
    """
    global REPO, API, RAW, MODELS_DIR, DOCS_URL, NAME, LOCAL_DIR
    fw = FRAMEWORKS[fw_name]
    REPO = fw["repo"]
    API = f"https://api.github.com/repos/{REPO}"
    RAW = f"https://raw.githubusercontent.com/{REPO}/{fw['branch']}"
    MODELS_DIR = fw["models_dir"]
    DOCS_URL = fw["docs"]
    NAME = fw["label"]
    LOCAL_DIR = os.path.expanduser(local_dir) if local_dir else None


def read_source(rel_path):
    """Return the text of a repository-relative file.

    When LOCAL_DIR is set the file is read from disk; otherwise it is fetched
    from the GitHub raw CDN. Returns None on failure.
    """
    if LOCAL_DIR:
        p = os.path.join(LOCAL_DIR, rel_path)
        try:
            with open(p, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None
    from .http_utils import _get
    try:
        body, _ = _get(f"{RAW}/{rel_path}")
    except RuntimeError:
        return None
    return body
