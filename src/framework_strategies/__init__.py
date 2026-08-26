"""Framework strategies: each framework is a strategy instance."""

from .base import FrameworkStrategy
from .sglang import SglangStrategy
from .vllm import VllmStrategy
from .vllm_ascend import VllmAscendStrategy

STRATEGIES = {s.name: s() for s in (VllmStrategy, SglangStrategy, VllmAscendStrategy)}

__all__ = ["FrameworkStrategy", "STRATEGIES"]
