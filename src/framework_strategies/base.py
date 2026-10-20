"""Base strategy class for framework-specific behavior."""

import json
import os
import re
import subprocess
import urllib.parse
from typing import Optional, Tuple

from ..context import Context
from ..http_utils import BROWSER_UA, _get, _get_json

# Release tags we are willing to report as a "first version".  Deliberately
# excludes synthetic tags such as ``proto-v0.2.0`` that some mirrors use.
_STABLE_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
_RELEASE_TAG_RE = re.compile(
    r"^v\d+\.\d+(?:\.\d+)?(?:[-.]?(?:rc|a|b|post)\d+)?$", re.IGNORECASE
)


class FrameworkStrategy:
    name = None
    label = None
    repo = None
    branch = None
    models_dir = None
    docs_url = None

    def make_context(self, local_dir: Optional[str] = None) -> Context:
        return Context.from_strategy(self, local_dir)

    def checkout_problem(self, path: str) -> Optional[str]:
        """Return why *path* does not look like a usable checkout, or None.

        The models directory is the common anchor, but not every framework
        keeps an ``__init__.py`` in it: SGLang's models directory is a PEP 420
        namespace package.  Check for the directory and at least one Python
        file instead of assuming a regular package.
        """
        models = os.path.join(path, self.models_dir)
        try:
            names = os.listdir(models)
        except OSError:
            return f"{self.models_dir} not found under {path}"
        if not any(name.endswith(".py") for name in names):
            return f"{self.models_dir} contains no Python files under {path}"
        return None

    def check_docs(self, arch: str, verbose: bool = False) -> str:
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

    def check_support(
        self, arch: str, ctx: Context, token: Optional[str] = None, verbose: bool = False
    ) -> Tuple[bool, Optional[str]]:
        if ctx.is_local:
            return self._check_local(arch, ctx, verbose)

        if token:
            inner = "^" + ctx.models_dir.replace("/", r"\/") + r"\/"
            q = f"{arch} repo:{ctx.repo} path:/{inner}/"
            url = f"{ctx.api}/search/code?q={urllib.parse.quote(q)}&per_page=20"
            data = _get_json(url, token)
            if data:
                for item in data.get("items", []):
                    if item["path"].startswith(ctx.models_dir) and item["path"].endswith(".py"):
                        if verbose:
                            print(f"  [github] code-search hit: {item['path']}")
                        return True, item["path"]
            elif verbose:
                print("  [github] code search returned nothing / was rate-limited.")

        if not token and verbose:
            print("  [github] no token: using best-effort tree scrape "
                  "(may be incomplete; set GITHUB_TOKEN for a definitive answer).")
        files = self.list_model_files(ctx, verbose)
        candidates = self.match_files(arch, files) if files else []
        if verbose:
            print("  [github] fallback candidates: " + ", ".join(candidates) or "(none)")
        for fname in candidates:
            path = f"{ctx.models_dir}/{fname}"
            body = ctx.read_source(path)
            if body and arch in body:
                if verbose:
                    print(f"  [github] '{arch}' found in {path}")
                return True, path
        return False, None

    def get_version(
        self, file_path: str, ctx: Context, token: Optional[str] = None, verbose: bool = False
    ) -> Optional[str]:
        if not file_path:
            return None
        if ctx.is_local:
            return self._get_version_local(file_path, ctx, verbose)
        try:
            date = self._earliest_commit_date(file_path, ctx, token)
        except RuntimeError as e:
            return f"unknown ({e}; try GITHUB_TOKEN)"
        if verbose:
            print(f"  [version] earliest commit touching {file_path}: {date}")
        if not date:
            return "unknown"
        try:
            return self._first_release_after(date, ctx, token)
        except RuntimeError as e:
            return f"unknown ({e}; try GITHUB_TOKEN)"

    def version_path(self, file_path: Optional[str]) -> Optional[str]:
        return file_path

    def extra_checks(self, arch: str, ctx: Context, token: Optional[str], verbose: bool, ref: Optional[str] = None):
        return None

    def list_py_files(self, ctx: Context, rel_dir: str, verbose: bool = False) -> set:
        """List ``.py`` files in a repository-relative directory."""
        if ctx.is_local:
            d = os.path.join(ctx.local_dir, rel_dir)
            try:
                return {f for f in os.listdir(d) if f.endswith(".py")}
            except OSError:
                if verbose:
                    print(f"  [local] could not list directory {d}.")
                return set()

        data = _get_json(f"{ctx.api}/contents/{rel_dir}")
        if isinstance(data, list):
            return {
                e["name"] for e in data
                if e.get("type") == "file" and e["name"].endswith(".py")
            }

        turl = f"https://github.com/{ctx.repo}/tree/{ctx.branch}/{rel_dir}"
        try:
            body, _ = _get(turl, ua=BROWSER_UA)
        except RuntimeError:
            return set()
        return set(re.findall(r'"name":"([a-zA-Z0-9_]+\.py)"', body or ""))

    def format_summary_extra(self, info) -> None:
        pass

    def list_model_files(self, ctx: Context, verbose: bool = False) -> Optional[set]:
        if ctx.is_local:
            d = os.path.join(ctx.local_dir, ctx.models_dir)
            try:
                names = {f for f in os.listdir(d) if f.endswith(".py")}
            except OSError:
                if verbose:
                    print(f"  [local] could not list models directory {d}.")
                return None
            names.discard("__init__.py")
            if names:
                if verbose:
                    print(f"  [local] listed {len(names)} model files from {d}.")
                return names
            return None

        url = f"{ctx.api}/contents/{ctx.models_dir}"
        data = _get_json(url)
        if data:
            names = {
                e["name"]
                for e in data
                if e.get("type") == "file" and e["name"].endswith(".py")
            }
            names.discard("__init__.py")
            if names:
                if verbose:
                    print(f"  [github] listed {len(names)} model files via Contents API.")
                return names

        if verbose:
            print("  [github] Contents API unavailable; scraping tree page.")
        turl = f"https://github.com/{ctx.repo}/tree/{ctx.branch}/{ctx.models_dir}"
        try:
            body, _ = _get(turl, ua=BROWSER_UA)
        except RuntimeError:
            body = None
        if not body:
            if verbose:
                print("  [github] could not fetch models directory listing.")
            return None
        names = set(re.findall(r'"name":"([a-zA-Z0-9_]+\.py)"', body))
        names.discard("__init__.py")
        return names

    @staticmethod
    def match_files(arch: str, files: set) -> list:
        a = arch.lower().replace("_", "")
        fam = re.match(r"[A-Za-z]+", arch)
        fam = fam.group(0).lower() if fam else ""
        out = []
        for f in files:
            if not f.endswith(".py"):
                continue
            stem = f[:-3].lower().replace("_", "")
            if (
                a.startswith(stem)
                or stem.startswith(a)
                or (fam and (stem.startswith(fam) or fam.startswith(stem)))
            ):
                out.append(f)
        return sorted(out, key=len)

    def _check_local(self, arch: str, ctx: Context, verbose: bool = False) -> Tuple[bool, Optional[str]]:
        files = self.list_model_files(ctx, verbose)
        candidates = self.match_files(arch, files) if files else []
        if verbose:
            print("  [local] candidates: " + (", ".join(candidates) or "(none)"))
        for fname in candidates:
            path = f"{ctx.models_dir}/{fname}"
            body = ctx.read_source(path)
            if body and arch in body:
                if verbose:
                    print(f"  [local] '{arch}' found in {path}")
                return True, path
        return False, None

    def _earliest_commit_date(self, path: str, ctx: Context, token: Optional[str]) -> Optional[str]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        url = f"{ctx.api}/commits?path={urllib.parse.quote(path)}&per_page=1"
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

    def _first_release_after(self, date_iso: str, ctx: Context, token: Optional[str]) -> str:
        rels = _get_json(f"{ctx.api}/releases?per_page=100", token) or []
        candidates = []
        for r in rels:
            tag = r.get("tag_name") or ""
            pub = r.get("published_at")
            if not pub or not _RELEASE_TAG_RE.match(tag):
                continue
            if pub >= date_iso:
                candidates.append(r)
        if not candidates:
            return "unreleased (main)"
        stable = [
            r for r in candidates
            if _STABLE_TAG_RE.match(r.get("tag_name") or "")
        ]
        pool = stable or candidates
        picked = min(pool, key=lambda r: r["published_at"])
        return picked["tag_name"]

    def _get_version_local(self, file_path: str, ctx: Context, verbose: bool = False) -> str:
        repo = ctx.local_dir
        log = subprocess.run(
            ["git", "-C", repo, "log", "--follow", "--diff-filter=AC",
             "--format=%H%x00%aI", "--", file_path],
            capture_output=True, text=True,
        )
        if log.returncode != 0 or not log.stdout.strip():
            if verbose:
                print(f"  [version] no git history for {file_path}.")
            return "unknown"
        # The log is newest-first, so take the first line: the latest add
        # commit.  ``--diff-filter=AC`` keeps plain adds and copies but drops
        # reverts (D) and pure renames (R); ``--follow`` walks rename history.
        # A revert/re-add therefore anchors at the re-add -- including the
        # vLLM-Ascend case where Git records the re-add as a copy (C062) --
        # instead of the older file it was copied/renamed from.
        first_line = log.stdout.strip().splitlines()[0]
        first_hash, _, first_date = first_line.partition("\x00")
        if verbose:
            print(f"  [version] latest add commit touching {file_path}: "
                  f"{first_date} ({first_hash[:12]})")

        # Only tags that actually contain the implementation commit are
        # candidates.  Sorting by creatordate and filtering to real release
        # tags avoids synthetic ``proto-*`` tags and "a tag created later but
        # on an unrelated branch" false positives.
        tags = subprocess.run(
            ["git", "-C", repo, "tag", "--contains", first_hash,
             "--sort=creatordate"],
            capture_output=True, text=True,
        )
        if tags.returncode != 0:
            return "unreleased (main)"
        release_tags = [
            t.strip() for t in tags.stdout.splitlines()
            if t.strip() and _RELEASE_TAG_RE.match(t.strip())
        ]
        stable_tags = [t for t in release_tags if _STABLE_TAG_RE.match(t)]
        picked = (stable_tags or release_tags)
        if verbose:
            print(f"  [version] release tags containing the commit: "
                  f"{', '.join(picked) or '(none)'}")
        return picked[0] if picked else "unreleased (main)"
