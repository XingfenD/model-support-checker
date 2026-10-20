"""Small git-fixture helpers for the regression tests."""

import os
import subprocess

_GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(repo, *args, env=None):
    e = os.environ.copy()
    e.update(_GIT_IDENTITY)
    if env:
        e.update(env)
    return subprocess.run(
        ["git", "-C", repo, *args],
        check=True,
        capture_output=True,
        text=True,
        env=e,
    )


def init_repo(path):
    os.makedirs(path, exist_ok=True)
    git(path, "init", "-q")
    return path


def write(repo, rel_path, content):
    path = os.path.join(repo, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def commit(repo, message, date="2026-09-10T00:00:00+00:00"):
    git(repo, "add", "-A")
    git(
        repo,
        "commit",
        "-q",
        "-m",
        message,
        env={"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date},
    )
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def tag(repo, name, date="2026-09-10T00:00:00+00:00"):
    git(
        repo,
        "tag",
        "-a",
        name,
        "-m",
        name,
        env={"GIT_COMMITTER_DATE": date},
    )
