"""Step 1: resolve a model's architecture name from its config.json."""

import json

from .http_utils import _get, _get_json


def get_architecture(model_id, source="auto"):
    """Return (architectures: list[str], source_used: str)."""
    if source in ("auto", "hf"):
        url = f"https://huggingface.co/{model_id}/resolve/main/config.json"
        body, _ = _get(url)
        if body:
            try:
                data = json.loads(body)
                if data.get("architectures"):
                    return data["architectures"], "huggingface"
            except json.JSONDecodeError:
                pass

    if source in ("auto", "modelscope"):
        url = f"https://modelscope.cn/models/{model_id}/resolve/master/config.json"
        body, _ = _get(url)
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
        f"Could not fetch config.json for '{model_id}' from HuggingFace or ModelScope."
    )
