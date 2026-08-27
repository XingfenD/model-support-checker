"""Minimal HTTP helpers (standard library only)."""

import json
import urllib.error
import urllib.request

UA = {"User-Agent": "model-support-check/1.0"}


def _get(url, headers=None, timeout=25, ua=None):
    h = dict(ua or UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), r.headers
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise RuntimeError(f"GitHub rate limit / forbidden ({e.code})")
        if e.code in (401, 404):
            return None, e.headers
        raise


def _get_json(url, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        body, _ = _get(url, headers)
    except RuntimeError:
        return None
    if body is None:
        return None
    return json.loads(body)
