"""Health checks for persisted setup state.

The `doctor()` function inspects `.state/state.json` and the configured
framework checkouts, returning a list of actionable issues. It is run
automatically on every invocation so callers (human or agent) do not need
to manually inspect `.state/` with `ls` or `cat`.
"""

import os

from ..framework_strategies import STRATEGIES
from .constants import STATE_FILE


class Issue:
    """A single doctor issue with severity and an actionable message."""

    def __init__(self, severity, message, framework=None):
        self.severity = severity  # "error" | "warning"
        self.message = message
        self.framework = framework

    def __str__(self):
        prefix = "ERROR" if self.severity == "error" else "WARN"
        if self.framework:
            return f"[{prefix} {self.framework}] {self.message}"
        return f"[{prefix}] {self.message}"


def doctor(st, args=None, framework=None):
    """Check setup state and local checkouts.

    Args:
        st: The loaded state dict, or None if no state file exists.
        args: Optional argparse namespace with path overrides.
        framework: Framework name to limit the check to, or None/'all' to check
            every configured framework.

    Returns:
        A list of Issue objects. An empty list means the configuration looks
        healthy enough to proceed.
    """
    issues = []

    if st is None:
        issues.append(
            Issue(
                "error",
                f"No setup state found ({STATE_FILE} missing). "
                "Run: python3 main.py --setup local",
            )
        )
        return issues

    mode = st.get("mode")
    if mode not in ("local", "token"):
        issues.append(
            Issue(
                "error",
                f"Invalid mode '{mode}' in state. Run: python3 main.py --setup local",
            )
        )
        return issues

    if mode == "token":
        token = _get_token(args)
        if not token:
            issues.append(
                Issue(
                    "warning",
                    "GitHub token mode but no GITHUB_TOKEN set. "
                    "Code search results will be best-effort only.",
                )
            )
        return issues

    # Local mode: validate the requested framework path(s).
    frameworks = list(STRATEGIES) if framework in (None, "all") else [framework]
    for fw_name in frameworks:
        if fw_name not in STRATEGIES:
            issues.append(Issue("error", f"Unknown framework: {fw_name}"))
            continue
        strategy = STRATEGIES[fw_name]
        path_key = f"{fw_name.replace('-', '_')}_path"
        configured_path = st.get(path_key)
        override_path = _get_override_path(args, fw_name)
        path = override_path or configured_path

        if not configured_path and not override_path:
            issues.append(
                Issue(
                    "error",
                    f"No local checkout configured. Run: python3 main.py --setup local --{fw_name}-path /path/to/{fw_name}",
                    framework=strategy.label,
                )
            )
            continue

        if override_path and not configured_path:
            issues.append(
                Issue(
                    "warning",
                    f"Using one-time override {override_path}; state is missing a saved path.",
                    framework=strategy.label,
                )
            )

        if not os.path.isdir(path):
            issues.append(
                Issue(
                    "error",
                    f"Configured path does not exist: {path}",
                    framework=strategy.label,
                )
            )
            continue

        if not os.path.isdir(os.path.join(path, ".git")):
            issues.append(
                Issue(
                    "error",
                    f"Path is not a git repository: {path}",
                    framework=strategy.label,
                )
            )
            continue

        init_file = os.path.join(path, strategy.models_dir, "__init__.py")
        if not os.path.isfile(init_file):
            issues.append(
                Issue(
                    "warning",
                    f"{strategy.models_dir}/__init__.py not found under {path}; "
                    "is this really a checkout?",
                    framework=strategy.label,
                )
            )

    return issues


def _get_token(args):
    if args and getattr(args, "token", None):
        return args.token
    return os.environ.get("GITHUB_TOKEN")


def _get_override_path(args, fw_name):
    if args is None:
        return None
    attr = f"{fw_name.replace('-', '_')}_path"
    return getattr(args, attr, None)


def print_report(issues):
    """Print doctor issues in a consistent format.

    Returns True if any errors were reported.
    """
    has_errors = any(i.severity == "error" for i in issues)
    if not issues:
        print("doctor: setup state looks healthy.")
        return False

    print("=== doctor ===")
    for issue in issues:
        print(f"  {issue}")
    print()
    return has_errors
