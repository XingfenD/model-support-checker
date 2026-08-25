"""Background checkout refresh."""

import subprocess
import threading


def fetch_status(path, result, key):
    """Background worker: `git fetch` a local checkout and count how far
    behind its upstream it is. Writes into result[key]; NEVER raises — any
    failure is recorded as {"error": ...} so the main flow is never blocked."""
    info = {"path": path}
    try:
        remotes = subprocess.run(
            ["git", "-C", path, "remote"],
            capture_output=True, text=True,
        ).stdout.strip()
        if not remotes:
            info["no_upstream"] = True
            result[key] = info
            return
        f = subprocess.run(
            ["git", "-C", path, "fetch", "--quiet", "origin"],
            capture_output=True, text=True, timeout=300,
        )
        if f.returncode != 0:
            lines = [ln for ln in f.stderr.strip().splitlines() if ln.strip()]
            info["error"] = lines[-1] if lines else "git fetch failed"
        else:
            up = subprocess.run(
                ["git", "-C", path, "rev-parse", "--abbrev-ref",
                 "--symbolic-full-name", "@{upstream}"],
                capture_output=True, text=True,
            )
            head = subprocess.run(
                ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            if up.returncode != 0 or head in ("", "HEAD"):
                info["no_upstream"] = True
            else:
                cnt = subprocess.run(
                    ["git", "-C", path, "rev-list", "--count",
                     f"HEAD..{up.stdout.strip()}"],
                    capture_output=True, text=True,
                )
                if cnt.returncode == 0 and cnt.stdout.strip().isdigit():
                    info["behind"] = int(cnt.stdout.strip())
                else:
                    info["no_upstream"] = True
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        # ponytail: broad catch is the point — refresh must never be fatal
        info["error"] = str(e)
    result[key] = info


def start_refresh(framework_paths):
    """Spawn daemon threads to refresh local checkouts concurrently.

    Returns (results_dict, threads); results are filled in as workers finish.
    """
    results = {}
    threads = []
    for key, path in framework_paths.items():
        t = threading.Thread(target=fetch_status, args=(path, results, key),
                             daemon=True)
        t.start()
        threads.append(t)
    return results, threads
