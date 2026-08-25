"""Execution context for framework checks.

Replaces the global mutable state in config.py. Each check runs with its own
Context, making the code concurrency-safe and easier to test.
"""

import os
from dataclasses import dataclass
from typing import Optional

from .http_utils import _get


@dataclass
class Context:
    """Immutable context for a single framework check."""
    
    repo: str
    branch: str
    models_dir: str
    docs_url: str
    label: str
    local_dir: Optional[str] = None
    
    @property
    def api(self) -> str:
        return f"https://api.github.com/repos/{self.repo}"
    
    @property
    def raw(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}"
    
    @property
    def is_local(self) -> bool:
        return self.local_dir is not None
    
    def read_source(self, rel_path: str) -> Optional[str]:
        """Read a repository-relative file.
        
        Local mode: read from disk.
        Remote mode: fetch from GitHub raw CDN.
        Returns None on failure.
        """
        if self.is_local:
            p = os.path.join(self.local_dir, rel_path)
            try:
                with open(p, encoding="utf-8") as f:
                    return f.read()
            except OSError:
                return None
        try:
            body, _ = _get(f"{self.raw}/{rel_path}")
        except RuntimeError:
            return None
        return body
    
    @classmethod
    def from_strategy(cls, strategy, local_dir: Optional[str] = None) -> "Context":
        """Create a Context from a strategy instance."""
        return cls(
            repo=strategy.repo,
            branch=strategy.branch,
            models_dir=strategy.models_dir,
            docs_url=strategy.docs_url,
            label=strategy.label,
            local_dir=os.path.expanduser(local_dir) if local_dir else None,
        )
