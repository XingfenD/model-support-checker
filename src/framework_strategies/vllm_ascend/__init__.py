"""vLLM-Ascend framework strategy."""

from .registry import (
    check_vllm_ascend_registry,
    fetch_vllm_ascend_registry,
    parse_vllm_ascend_registry,
)
from .strategy import VllmAscendStrategy

__all__ = [
    "VllmAscendStrategy",
    "fetch_vllm_ascend_registry",
    "parse_vllm_ascend_registry",
    "check_vllm_ascend_registry",
]
