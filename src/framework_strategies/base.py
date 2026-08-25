"""Base strategy class for framework-specific behavior."""

import re
from typing import Optional, Tuple

from ..check import check_support, get_version
from ..context import Context
from ..http_utils import _get


class FrameworkStrategy:
    name = None
    label = None
    repo = None
    branch = None
    models_dir = None
    docs_url = None

    def make_context(self, local_dir: Optional[str] = None) -> Context:
        """Create a Context for this strategy."""
        return Context.from_strategy(self, local_dir)

    def check_docs(self, arch: str, verbose: bool = False) -> str:
        """Best-effort check of the framework's official docs."""
        body, _ = _get(self.docs_url)
        if not body:
            if verbose:
                print(f"  [docs] could not fetch {self.docs_url} (may be JS-rendered).")
            return "unknown"
        if arch in body or arch.lower() in body.lower():
            return "yes"
        family = re.split(r"(?=[A-Z])", arch)[0].lower()
        if family and family in body.lower():
            return "maybe"
        return "no"

    def check_support(
        self, arch: str, ctx: Context, token: Optional[str] = None, verbose: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Check if the architecture is supported. Returns (supported, file_path)."""
        return check_support(arch, ctx, token, verbose)

    def get_version(
        self, file_path: str, ctx: Context, token: Optional[str] = None, verbose: bool = False
    ) -> Optional[str]:
        """Get the first version that supports the architecture."""
        return get_version(file_path, ctx, token, verbose)

    def version_path(self, file_path: Optional[str]) -> Optional[str]:
        """Return the path to use for version detection."""
        return file_path

    def extra_checks(self, arch: str, ctx: Context, token: Optional[str], verbose: bool, ref: Optional[str] = None):
        """Framework-specific extra checks. Returns extra info or None."""
        return None

    def format_summary_extra(self, info) -> None:
        """Format framework-specific extra info in summary."""
        pass
