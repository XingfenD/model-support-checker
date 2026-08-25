"""State management for model-support-checker.

State lives in <skill root>/.state/ (gitignored via .gitignore) so the
first-run choice (GitHub PAT vs local clone) survives across runs without
being tracked by git. The GitHub token itself is NEVER stored here.
"""

from .persistence import load, save, reset
from .setup import first_run_menu, ensure_setup
from .refresh import start_refresh

__all__ = ["load", "save", "reset", "first_run_menu", "ensure_setup", "start_refresh"]
