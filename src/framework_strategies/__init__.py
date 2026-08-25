"""Framework strategies: each framework is a strategy instance."""

from .base import FrameworkStrategy
from .sglang import SglangStrategy
from .vllm import VllmStrategy

STRATEGIES = {s.name: s() for s in (VllmStrategy, SglangStrategy)}

__all__ = ["FrameworkStrategy", "STRATEGIES"]
