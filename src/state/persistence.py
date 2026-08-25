"""State persistence: load, save, reset."""

import json
import os

from .constants import STATE_DIR, STATE_FILE, REPOS_DIR


def load():
    """Return the saved state dict, or None if not set up yet."""
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            st = json.load(f)
        return st if isinstance(st, dict) and st.get("mode") else None
    except (OSError, ValueError):
        return None


def save(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)
    return st


def reset():
    """Forget setup state. Cloned repos under .state/repos/ are kept and will
    be reused automatically by a later `--setup local`."""
    try:
        os.remove(STATE_FILE)
        print(f"Removed {STATE_FILE} (cloned repos kept at {REPOS_DIR}).")
    except FileNotFoundError:
        print("No saved state found.")
