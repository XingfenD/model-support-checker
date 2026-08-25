"""State constants."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(ROOT, ".state")
REPOS_DIR = os.path.join(STATE_DIR, "repos")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
