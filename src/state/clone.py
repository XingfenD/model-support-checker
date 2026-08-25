"""Repository cloning and validation."""

import os
import subprocess

from ..framework_strategies import STRATEGIES
from .constants import REPOS_DIR


def clone(url, target):
    """Clone url into target (full history -- shallow clones break step 4)."""
    if os.path.isdir(os.path.join(target, ".git")):
        print(f"  reusing existing clone: {target}")
        return target
    os.makedirs(os.path.dirname(target), exist_ok=True)
    print(f"  cloning {url} -> {target} (full history, may take a while)...")
    r = subprocess.run(["git", "clone", url, target])
    if r.returncode != 0:
        raise RuntimeError(f"git clone failed for {url}")
    return target


def validate_checkout(path, fw_name):
    """Validate that a path looks like a valid framework checkout."""
    strategy = STRATEGIES[fw_name]
    if not os.path.isfile(os.path.join(path, strategy.models_dir, "__init__.py")):
        print(
            f"  WARNING: {strategy.models_dir} not found under {path}; "
            f"is this really a {strategy.label} checkout?"
        )


def get_clone_url(fw_name):
    """Get the clone URL for a framework."""
    return f"https://github.com/{STRATEGIES[fw_name].repo}"


def get_default_clone_path(fw_name):
    """Get the default clone path for a framework."""
    return os.path.join(REPOS_DIR, fw_name)
