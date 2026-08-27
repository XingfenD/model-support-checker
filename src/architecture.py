"""Step 1: resolve a model's architecture name from its config.json."""

import json

from .http_utils import _get, _get_json


def get_architecture(model_id, source="modelscope", arch_override=None):
    """Return (architectures: list[str], source_used: str).

    If *arch_override* is given (comma-separated architecture string), return it
    directly without fetching config.json.  This allows the caller to bypass
    the network lookup when the config is unavailable or the user already knows
    the architecture name.
    """
    if arch_override:
        archs = [a.strip() for a in arch_override.split(",") if a.strip()]
        if archs:
            return archs, "manual"

    if source in ("auto", "hf"):
        url = f"https://huggingface.co/{model_id}/resolve/main/config.json"
        try:
            body, _ = _get(url)
        except RuntimeError:
            body = None
        if body:
            try:
                data = json.loads(body)
                if data.get("architectures"):
                    return data["architectures"], "huggingface"
            except json.JSONDecodeError:
                pass

    if source in ("auto", "modelscope"):
        url = f"https://modelscope.cn/models/{model_id}/resolve/master/config.json"
        try:
            body, _ = _get(url)
        except RuntimeError:
            body = None
        if body:
            try:
                data = json.loads(body)
                if data.get("architectures"):
                    return data["architectures"], "modelscope"
            except json.JSONDecodeError:
                pass
        api = f"https://modelscope.cn/api/v1/models/{model_id}"
        data = _get_json(api)
        if data:
            arch = data.get("Architectures") or data.get("architectures")
            if arch:
                return [arch] if isinstance(arch, str) else arch, "modelscope-api"

    raise RuntimeError(
        f"Could not fetch config.json for '{model_id}' from HuggingFace or ModelScope.\n"
        f"Try: --source hf | --source modelscope  (pick a specific platform)\n"
        f"  or: --arch <ArchitectureName>          (e.g. --arch LlamaForCausalLM)"
    )
