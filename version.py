"""Step 4: approximate the first framework release that supports the model."""

import json
import re
import urllib.parse

import config
from http_utils import _get, _get_json


def _earliest_commit_date(path, token):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{config.API}/commits?path={urllib.parse.quote(path)}&per_page=1"
    try:
        body, hdrs = _get(url, headers)
    except RuntimeError as e:
        raise RuntimeError(str(e)) from e
    if not body:
        return None
    link = hdrs.get("Link", "")
    last_page = 1
    for part in link.split(","):
        if 'rel="last"' in part:
            m = re.search(r"[?&]page=(\d+)", part)
            if m:
                last_page = int(m.group(1))
    if last_page > 1:
        try:
            body, _ = _get(f"{url}&page={last_page}", headers)
        except RuntimeError:
            body = None
        if not body:
            return None
    commits = json.loads(body)
    if not commits:
        return None
    commit = commits[-1]["commit"]
    return commit.get("committer", {}).get("date") or commit.get("author", {}).get("date")


def _first_release_after(date_iso, token):
    rels = _get_json(f"{config.API}/releases?per_page=100", token) or []
    picked = None
    for r in rels:
        pub = r.get("published_at")
        if not pub:
            continue
        if pub >= date_iso and (picked is None or pub < picked["published_at"]):
            picked = r
    return picked["tag_name"] if picked else "unreleased (main)"


def get_version(file_path, token, verbose=False):
    if not file_path:
        return None
    try:
        date = _earliest_commit_date(file_path, token)
    except RuntimeError as e:
        return f"unknown ({e}; try GITHUB_TOKEN)"
    if verbose:
        print(f"  [version] earliest commit touching {file_path}: {date}")
    if not date:
        return "unknown"
    try:
        return _first_release_after(date, token)
    except RuntimeError as e:
        return f"unknown ({e}; try GITHUB_TOKEN)"
