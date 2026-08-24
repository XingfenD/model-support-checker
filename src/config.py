"""Framework configuration and active-framework state for model-support-checker."""

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


def set_active(fw_name):
    """Initialise the active-framework globals from FRAMEWORKS[fw_name]."""
    global REPO, API, RAW, MODELS_DIR, DOCS_URL, NAME
    fw = FRAMEWORKS[fw_name]
    REPO = fw["repo"]
    API = f"https://api.github.com/repos/{REPO}"
    RAW = f"https://raw.githubusercontent.com/{REPO}/{fw['branch']}"
    MODELS_DIR = fw["models_dir"]
    DOCS_URL = fw["docs"]
    NAME = fw["label"]
