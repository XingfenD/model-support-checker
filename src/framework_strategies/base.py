"""Base strategy class for framework-specific behavior."""

import re

from .. import config
from ..http_utils import _get


class FrameworkStrategy:
    name = None
    label = None
    repo = None
    branch = None
    models_dir = None
    docs_url = None

    def activate(self, local_dir=None):
        config.set_active(self, local_dir)

    def check_docs(self, arch, verbose=False):
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

    def extra_checks(self, arch, token, verbose, ref=None):
        return None

    def version_path(self, file_path):
        return file_path

    def format_summary_extra(self, info):
        pass
