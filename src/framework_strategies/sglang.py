"""SGLang strategy."""

from .base import FrameworkStrategy


class SglangStrategy(FrameworkStrategy):
    name = "sglang"
    label = "SGLang"
    repo = "sgl-project/sglang"
    branch = "main"
    models_dir = "python/sglang/srt/models"
    docs_url = "https://docs.sglang.io/docs/supported-models"
