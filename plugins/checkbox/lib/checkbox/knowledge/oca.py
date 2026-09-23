"""OCA module catalog: build a local per-version index and rank it.

docs/ARCHITECTURE.md §7.1's "oca" row: curated OCA repositories, branch =
version; manifest fields (name, summary, development_status, maintainers) +
last commit date. That row is now built -- this is D10's revisit trigger made
real ("a real user names a specific OCA module search need"); the runtime
constraint that originally deferred it (a full shallow clone of OCA is a lot
of disk) was measured away during design: a `--filter=blob:none` +
sparse-checkout-of-manifests-only clone of OCA/sale-workflow@18.0 transfers
~1 MB and checks out ~1.8 MB, and `git log -1` on the same shallow clone
frees the last-commit date for the maintenance flag.

Source of truth is github.com/OCA directly. The alternatives were evaluated
against real output before building (docs/ARCHITECTURE.md §14 D15):

- **PyPI JSON API** (`pypi.org/pypi/odoo-addon-<name>-<ver>/json`): rich and
  structured where it exists, but versioned-suffix packages
  (`odoo-addon-<name>-17.0`) return 404 -- verified -- so per-Odoo-version
  availability has to be inferred from release history; there is no
  prefix-search/enumeration API (the `simple/` index is ~100 MB of HTML);
  coverage is derived and partial (not every OCA repo publishes); and it
  carries neither `development_status`/`maintainers` nor a commit date.
- **apps.odoo.com**: `apps/modules/18.0` returns 200 but its HTML contains
  zero module links (JS-rendered Odoo site; module pages 301-redirect).

Repo enumeration calls the GitHub org-repos endpoint exactly 3 times (3
100-entry pages, ~2% of the unauthenticated 60 req/hr budget), and the
result is cached so a rebuild never needs the API again. Per-repo content
travels over the git protocol, which is not under that rate limit.

The build command needs a `git` executable on PATH. Searching a built index
needs only the stdlib.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from checkbox import paths
from checkbox.knowledge.source import read_manifest

GITHUB_ORG_REPOS_URL = "https://api.github.com/orgs/OCA/repos?per_page=100&page={page}"
REPO_BASE_URL = "https://github.com/OCA/{repo}"
# 100 repos per page; 20 pages = 2000 repos, far past OCA's ~270, and a hard stop
# against a misbehaving API that never returns a short page.
MAX_REPO_PAGES = 20

# Concurrent `git clone`s during a build. The work is network/git bound and each
# repo is ~1-2 MB, so a few in flight cuts the ~18 min sequential run a lot
# without hammering GitHub.
BUILD_JOBS = 4

# An interrupted build's checkpoint older than this is ignored (repos move on).
PARTIAL_MAX_AGE_SECONDS = 24 * 3600
USER_AGENT = "checkbox-odoo (OCA module index builder)"

# Meta or duplicate-catalog repos whose clone is pure waste. OCB is a full
# Odoo fork whose modules are Odoo core -- already in the source index, and
# its tree is large. Kept deliberately small and pinned; anything else just
# gets cloned and contributes nothing if it has no manifests on that branch.
NON_MODULE_REPOS = frozenset(
    {
        ".github",
        "OCB",
        "OpenUpgrade",
        "contribute-md-template",
        "docs",
        "maintainer-quality-tools",
        "maintainer-tools",
        "oca-addons-repo-template",
        "odoo-community.org",
    }
)

# A module whose last commit is older than this counts as stale/unmaintained
# in the output flag. 18 months: longer than an Odoo major release cycle, so
# a maintained module almost always gets touched between release trains.
STALE_DAYS = 540

VERSION_RE = re.compile(r"\d+\.\d+")

_STOPWORDS = frozenset(
    {
        "a",
        "add",
        "adds",
        "an",
        "and",
        "for",
        "from",
        "in",
        "modules",
        "of",
        "on",
        "the",
        "to",
        "with",
    }
)

# Searches rank in memory over `load_catalog`, so no FTS table is needed --
# the catalog is a few thousand rows, small enough to score on every query.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS modules (
    technical_name TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT NOT NULL,
    license TEXT,
    version TEXT NOT NULL,
    repo TEXT NOT NULL,
    category TEXT,
    depends TEXT,
    development_status TEXT,
    maintainers TEXT,
    author TEXT,
    last_commit TEXT,
    website TEXT
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


@dataclass
class BuildStats:
    version: str
    repos_total: int = 0
    repos_excluded: int = 0
    repos_no_branch: int = 0
    repos_failed: int = 0
    repos_indexed: int = 0
    modules: int = 0
    elapsed_seconds: float = 0.0
    db_path: str = ""
    already_built: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "repos_total": self.repos_total,
            "repos_excluded": self.repos_excluded,
            "repos_no_branch": self.repos_no_branch,
            "repos_failed": self.repos_failed,
            "repos_indexed": self.repos_indexed,
            "modules": self.modules,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "db_path": self.db_path,
            "already_built": self.already_built,
        }


# --------------------------------------------------------------------------
# Repo enumeration
# --------------------------------------------------------------------------


def fetch_repo_list() -> list[str]:
    """Return every OCA org repo name via the GitHub API (one request per
    100 repos, currently 3).

    Raises `urllib.error.HTTPError`/`URLError` on failure; callers fall back
    to the cached snapshot when the API is unavailable or rate-limited,
    since the OCA repo set changes slowly.
    """
    import urllib.error  # lazy: keeps hook start-up (which imports cli) fast
    import urllib.request

    names: list[str] = []
    for page in range(1, MAX_REPO_PAGES + 1):
        req = urllib.request.Request(
            GITHUB_ORG_REPOS_URL.format(page=page), headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise urllib.error.HTTPError(
                req.full_url, 502, "unexpected org repos payload", None, None
            )
        names.extend(
            item["name"] for item in payload if isinstance(item, dict) and item.get("name")
        )
        if len(payload) < 100:
            break
    return sorted(names)


def load_repo_snapshot(data_root: Path) -> list[str] | None:
    path = data_root / "repos.json"
    if not path.is_file():
        return None
    try:
        return sorted(json.loads(path.read_text(encoding="utf-8"))["repos"])
    except (ValueError, KeyError, OSError):
        return None


def save_repo_snapshot(data_root: Path, repos: list[str]) -> Path:
    data_root.mkdir(parents=True, exist_ok=True)
    path = data_root / "repos.json"
    path.write_text(
        json.dumps(
            {
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "repos": repos,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def enumerate_oca_repos(data_root: Path) -> list[str]:
    """Repo names for the build: GitHub API, falling back to a cached
    snapshot (e.g. a fresh rerun with the API rate-limited), and raising a
    clear error only when both are unavailable."""
    import urllib.error

    try:
        names = fetch_repo_list()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
        cached = load_repo_snapshot(data_root)
        if cached:
            print(
                f"oca: GitHub API unavailable ({exc}); using cached OCA repo "
                f"list from {data_root / 'repos.json'}",
                file=sys.stderr,
            )
            return cached
        raise RuntimeError(
            "cannot list OCA repositories: the GitHub org API is unreachable "
            f"({exc}) and no cached repo list exists yet at {data_root}/repos.json"
        ) from exc
    save_repo_snapshot(data_root, names)
    return names


# --------------------------------------------------------------------------
# Per-repo fetch (git partial clone)
# --------------------------------------------------------------------------


def _rmtree(path: Path) -> None:
    """`shutil.rmtree` that also removes git's read-only object files (which
    plain `ignore_errors=True` leaves behind on Windows) and never raises."""

    def _make_writable_and_retry(func, target, _exc):  # noqa: ANN001
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=_make_writable_and_retry)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run one git subprocess; None when it timed out or the binary died, so
    the build can count the repo as failed instead of crashing on a slow
    network. Callers accept that a returned process may be a failure."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (subprocess.TimeoutExpired, OSError):
        return None


def _branch_exists(url: str, version: str, git: str) -> bool:
    proc = _run([git, "ls-remote", "--heads", "--exit-code", url, f"refs/heads/{version}"])
    return proc is not None and proc.returncode == 0


def clone_repo(url: str, version: str, dest: Path, git: str) -> str | None:
    """Sparse-clone *url* at *version* and return the branch tip's commit
    date (`YYYY-MM-DD`), or None when the repo has no such branch.

    The first attempt uses `--filter=blob:none` (only tree objects plus the
    manifests travel; measured ~1 MB for a 170-module repo). Older git
    builds or servers that refuse partial clones fall back to a plain
    `--depth 1 --sparse` clone of the same branch. Never fetches blobs the
    sparse checkout doesn't ask for. Any git failure or timeout on a single
    repo is reported as "error" -- never raised -- so one slow repo can't
    abort a 268-repo build.
    """
    if not _branch_exists(url, version, git):
        return None
    attempts = [
        [
            git,
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            "--single-branch",
            "--branch",
            version,
            url,
            str(dest),
        ],
        # Fallback for git<2.22 / filters refused by the server.
        [
            git,
            "clone",
            "--depth",
            "1",
            "--sparse",
            "--single-branch",
            "--branch",
            version,
            url,
            str(dest),
        ],
    ]
    proc: subprocess.CompletedProcess[str] | None = None
    for cmd in attempts:
        proc = _run(cmd)
        if proc is not None and proc.returncode == 0:
            break
        _rmtree(dest)
    else:
        # Branch checked out fine but every clone attempt failed; let the
        # caller count this repo as failed rather than crash the build.
        print(
            f"oca: clone failed for {url} at {version} (git returned "
            f"{proc.returncode if proc else 'timeout/no-process'}) -- skipped",
            file=sys.stderr,
        )
        return "error"

    proc = _run([git, "-C", str(dest), "sparse-checkout", "set", "--no-cone", "*/__manifest__.py"])
    if proc is None or proc.returncode != 0:
        _rmtree(dest)
        return "error"
    log = _run([git, "-C", str(dest), "log", "-1", "--format=%cs"])
    if log is None:
        return "error"
    return log.stdout.strip() or "error"


# --------------------------------------------------------------------------
# Manifest → catalog row
# --------------------------------------------------------------------------


def _iter_module_manifests(repo_root: Path):
    """Yield every top-level `*/__manifest__.py` in a cloned repo worktree."""
    for child in sorted(repo_root.iterdir()):
        manifest = child / "__manifest__.py"
        # A symlinked dir or manifest could point outside the clone; skip it.
        if child.is_symlink() or manifest.is_symlink():
            continue
        if child.is_dir() and manifest.is_file():
            yield child, manifest


def _module_row(
    module_dir: Path,
    manifest_path: Path,
    version: str,
    repo: str,
    last_commit: str | None,
) -> dict[str, Any] | None:
    manifest = read_manifest(manifest_path)
    if manifest is None or manifest.get("installable") is False:
        return None
    return {
        "technical_name": module_dir.name,
        "name": sanitize_text(manifest.get("name") or module_dir.name, 200),
        "summary": sanitize_text(manifest.get("summary") or manifest.get("description"), 500),
        "license": _as_str(manifest.get("license")) or None,
        "version": version,
        "repo": repo,
        "category": _as_str(manifest.get("category")) or None,
        "depends": _as_list(manifest.get("depends")),
        "development_status": _as_str(manifest.get("development_status")) or None,
        "maintainers": _as_list(manifest.get("maintainers")),
        "author": _as_str(manifest.get("author")) or None,
        "last_commit": last_commit,
        "website": _as_str(manifest.get("website")) or None,
    }


def sanitize_text(text: Any, limit: int) -> str:
    """One printable line, at most *limit* chars. Manifest text is written by
    third parties and ends up in the agent's context, so it is flattened
    (no newlines/control characters to fake structure) and capped."""
    flat = "".join(ch if ch.isprintable() else " " for ch in str(text or ""))
    flat = " ".join(flat.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _ref_token(value: Any) -> str:
    """A `key=value` token value safe inside a card's `;`/`|`-delimited evidence."""
    token = "".join(ch if ch.isalnum() or ch in "-._+" else "_" for ch in str(value or ""))
    return token or "unknown"


def _as_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _index_worktree(
    repo_root: Path, repo: str, version: str, last_commit: str | None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for module_dir, manifest_path in _iter_module_manifests(repo_root):
        row = _module_row(module_dir, manifest_path, version, repo, last_commit)
        if row is not None:
            rows.append(row)
    return rows


# --------------------------------------------------------------------------
# Catalog storage
# --------------------------------------------------------------------------


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.executescript(_SCHEMA)
    con.commit()
    return con


def write_catalog(
    db_path: Path, rows: list[dict[str, Any]], extra: dict[str, str] | None = None
) -> int:
    """Write the catalog to a sibling temp file, then `os.replace` it into
    place, so a reader (or a crash) never sees a half-written or table-less
    database, and a rebuild never exposes an empty catalog."""
    db_path = Path(db_path)
    tmp = db_path.with_name(f".{db_path.name}.tmp-{os.getpid()}")
    tmp.unlink(missing_ok=True)
    con = connect(tmp)
    try:
        con.executemany(
            "INSERT OR REPLACE INTO modules "
            "(technical_name, name, summary, license, version, repo, category, depends, "
            " development_status, maintainers, author, last_commit, website) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    r["technical_name"],
                    r["name"],
                    r["summary"],
                    r.get("license"),
                    r["version"],
                    r["repo"],
                    r.get("category"),
                    json.dumps(r.get("depends") or []),
                    r.get("development_status"),
                    json.dumps(r.get("maintainers") or []),
                    r.get("author"),
                    r.get("last_commit"),
                    r.get("website"),
                )
                for r in rows
            ],
        )
        for key, value in (extra or {}).items():
            con.execute("INSERT OR REPLACE INTO meta (k, v) VALUES (?,?)", (key, value))
        con.commit()
    except BaseException:
        con.close()
        tmp.unlink(missing_ok=True)
        raise
    con.close()
    os.replace(tmp, db_path)
    return len(rows)


def built_versions(data_root: Path) -> list[str]:
    data_root = Path(data_root)
    if not data_root.is_dir():
        return []
    return sorted(p.stem for p in data_root.glob("[0-9]*.sqlite") if p.suffix == ".sqlite")


def load_catalog(db_path: Path) -> list[dict[str, Any]]:
    if not Path(db_path).is_file():
        return []
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT technical_name, name, summary, license, version, repo, category, "
            "depends, development_status, maintainers, author, last_commit, website "
            "FROM modules"
        ).fetchall()
    except sqlite3.Error as exc:
        # A corrupt/unreadable catalog must not take down `checkbox search`.
        print(f"oca: cannot read {db_path} ({exc}); rebuild with --force", file=sys.stderr)
        return []
    finally:
        con.close()
    return [
        {
            "technical_name": r[0],
            "name": r[1],
            "summary": r[2],
            "license": r[3],
            "version": r[4],
            "repo": r[5],
            "category": r[6],
            "depends": json.loads(r[7] or "[]"),
            "development_status": r[8],
            "maintainers": json.loads(r[9] or "[]"),
            "author": r[10],
            "last_commit": r[11],
            "website": r[12],
        }
        for r in rows
    ]


# --------------------------------------------------------------------------
# Ranking
# --------------------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    """Lowercased word tokens with separators dropped and stopwords/singles
    removed. Snake_case technical names come apart on the underscore, which
    is what lets a free-text query meet a module named `sale_tier_validation`."""
    words: list[str] = []
    for part in text.lower().split():
        for word in part.replace("_", " ").replace("-", " ").split():
            word = "".join(ch for ch in word if ch.isalnum())
            if word and word not in _STOPWORDS and len(word) > 1:
                words.append(word)
    return words


@dataclass
class _IndexedRow:
    row: dict[str, Any]
    tech: set[str]
    name: set[str]
    summary: set[str]
    extra: set[str]  # category + depends tokens


def _index_rows(rows: list[dict[str, Any]]) -> list[_IndexedRow]:
    indexed: list[_IndexedRow] = []
    for row in rows:
        tech = set(tokenize(row["technical_name"]))
        name = set(tokenize(row["name"]))
        summary = set(tokenize(row["summary"]))
        indexed.append(
            _IndexedRow(
                row=row,
                tech=tech,
                name=name,
                summary=summary,
                extra=set(tokenize(row.get("category") or ""))
                | set(tokenize(" ".join(row.get("depends") or []))),
            )
        )
    return indexed


def _is_exact_match(raw_query: str, technical_name: str) -> bool:
    """True when the raw query *is* a module's technical name, modulo word
    separators, so both `sale_tier_validation` and `sale tier validation`
    count -- and, because underscores are tokenized away, only a look at the
    raw string can detect it."""

    def norm(s: Any) -> str:
        return str(s).strip().lower().replace("_", " ")

    return norm(raw_query) == norm(technical_name)


def score_module(query_tokens: list[str], index: _IndexedRow, raw_query: str = "") -> float:
    """Deterministic keyword score: exact technical-name match wins outright,
    then weighted token hits (technical name 3 > display name 2 > summary 1 >
    category/depends 1), plus a small bonus for a prefix hit against a
    technical token (so "pricelist" still weak-matches "price_lock")."""
    if raw_query and _is_exact_match(raw_query, index.row["technical_name"]):
        return 1000.0
    score = 0.0
    for token in query_tokens:
        if token in index.tech:
            score += 3.0
        else:
            # One query term, many technical tokens (e.g. "sale") -- count
            # matching prefix once, not per hit, so a bare "price" doesn't
            # outrank the module whose summary also says price.
            score += (
                0.5 if any(t.startswith(token) and len(token) >= 4 for t in index.tech) else 0.0
            )
        if token in index.name:
            score += 2.0
        elif len(token) >= 4 and any(t.startswith(token) for t in index.name):
            score += 0.5  # "brand" still finds "Branding"
        if token in index.summary:
            score += 1.0
        else:
            score += 0.25 if any(t.startswith(token) for t in index.summary) else 0.0
        if token in index.extra:
            score += 1.0
    return score


def stale_date(last_commit: str | None, now_days: float | None = None) -> bool:
    """True when *last_commit* (`YYYY-MM-DD`) is older than STALE_DAYS.
    *now_days* (days since the epoch) is for tests; calendar dates, so no
    timezone or DST drift."""
    if not last_commit:
        return False
    try:
        commit = date.fromisoformat(last_commit)
    except ValueError:
        return False
    today = (
        date(1970, 1, 1) + timedelta(days=int(now_days)) if now_days is not None else date.today()
    )
    return (today - commit).days > STALE_DAYS


def to_evidence(row: dict[str, Any], score: float = 0.0) -> dict[str, Any]:
    """Evidence row for a catalog module. `last_commit`/`stale` are
    **repo-level**: the branch tip's commit date (a depth-1 clone has no
    per-module history), so a dead module in an active repo looks fresh and
    bot commits (translations, pre-commit) can mask abandonment."""
    ref = f"OCA/{row['repo']}/{row['technical_name']}"
    return {
        "kind": "oca",
        "ref": ref,
        # Paste this as the card's `oca | ...` evidence; `card validate` checks it.
        "card_ref": (
            f"{ref} branch={_ref_token(row['version'])} license={_ref_token(row.get('license'))}"
            f" last_commit={_ref_token(row.get('last_commit'))}"
        ),
        "third_party_text": True,
        "line": None,
        "title": f"{sanitize_text(row['name'], 200)} ({row['technical_name']})",
        "snippet": sanitize_text(row["summary"], 300),
        "version": row["version"],
        "score": score,
        "license": row.get("license"),
        "last_commit": row.get("last_commit"),
        "stale": stale_date(row.get("last_commit")),
        "development_status": row.get("development_status"),
        "maintainers": row.get("maintainers"),
        "depends": row.get("depends"),
        "source_url": f"https://github.com/OCA/{row['repo']}/tree/{row['version']}/{row['technical_name']}",
    }


def format_evidence(result: dict[str, Any]) -> list[str]:
    """Human-readable lines for one `kind: "oca"` evidence row."""
    lines = [f"[{result['kind']}] {result['title']} -- {result['ref']}"]
    if result["snippet"]:
        lines.append(f"    (third-party manifest text, unverified) {result['snippet']}")
    parts = [f"license: {result.get('license') or 'unknown'}"]
    if result.get("last_commit"):
        parts.append(f"repo last commit: {result['last_commit']}")
    if result.get("development_status"):
        parts.append(f"status: {result['development_status']}")
    if result.get("stale"):
        parts.append("STALE REPO: no commit on this branch in over 18 months")
    parts.append(f"branch: {result['version']}")
    lines.append(f"    {' | '.join(parts)}")
    if result.get("card_ref"):
        lines.append(f"    card evidence: oca | {result['card_ref']}")
    return lines


def search_catalog(query: str, db_path: Path, limit: int = 10) -> list[dict[str, Any]]:
    """Rank the catalog at *db_path* against free-text *query*.

    Returns Evidence-shaped dicts (kind "oca") sorted by descending score.
    An exact technical-name hit is a flat 1000; otherwise tokens score against
    the technical name, display name, summary and category/depends. Empty
    catalog or empty query yield [].
    """
    if not query.strip():
        return []
    rows = load_catalog(db_path)
    if not rows:
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    indexed = _index_rows(rows)
    scored = [(score_module(query_tokens, item, query), item.row) for item in indexed]
    scored = [pair for pair in scored if pair[0] > 0]
    scored.sort(key=lambda pair: (-pair[0], pair[1]["technical_name"]))
    return [to_evidence(row, score) for score, row in scored[:limit]]


def search_all_versions(query: str, data_root: Path, limit: int = 10) -> list[dict[str, Any]]:
    """Rank across every built OCA catalog; each result's `version`/`ref`
    keeps its real branch so "exists on 17.0, not on 18.0" is an explicit,
    deterministic fact instead of a guess."""
    if not query.strip():
        return []
    results: list[dict[str, Any]] = []
    for version in built_versions(data_root):
        results.extend(search_catalog(query, _db_path(data_root, version), limit=limit))
    results.sort(key=lambda r: (-r["score"], r["version"], r["ref"]))
    return results[:limit]


# --------------------------------------------------------------------------
# Build orchestration
# --------------------------------------------------------------------------


def _db_path(data_root: Path, version: str) -> Path:
    return Path(data_root) / f"{version}.sqlite"


def _acquire_build_lock(data_root: Path, version: str) -> Path:
    """Exclusive per-version build lock (`O_EXCL` file holding our pid). A
    lock whose pid is gone is stale and is taken over."""
    lock = data_root / f".build-{version}.lock"
    for _ in range(2):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                pid = int(lock.read_text().strip() or 0)
                os.kill(pid, 0)
            except (ValueError, ProcessLookupError, PermissionError, OSError) as exc:
                if isinstance(exc, PermissionError):  # pid exists, owned by someone else
                    pid = -1
                else:
                    lock.unlink(missing_ok=True)  # stale: retry once
                    continue
            raise RuntimeError(
                f"another `checkbox oca build` for {version} is running "
                f"(pid {pid}); if not, delete {lock}"
            ) from None
        with os.fdopen(fd, "w") as fh:
            fh.write(str(os.getpid()))
        return lock
    raise RuntimeError(f"cannot take build lock {lock}")


def _load_partial(path: Path) -> dict[str, dict[str, Any]]:
    """Per-repo outcomes checkpointed by an interrupted build (fresh only)."""
    if not path.is_file() or time.time() - path.stat().st_mtime > PARTIAL_MAX_AGE_SECONDS:
        path.unlink(missing_ok=True)
        return {}
    done: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
            done[entry["repo"]] = entry
        except (ValueError, KeyError, TypeError):
            continue  # torn last line from a kill mid-write
    return done


def _append_partial(path: Path, outcome: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(outcome) + "\n")


def _count_outcome(stats: BuildStats, rows: list[dict[str, Any]], outcome: dict[str, Any]) -> None:
    if outcome["status"] == "no_branch":
        stats.repos_no_branch += 1
    else:
        rows.extend(outcome["rows"])
        stats.repos_indexed += 1
        stats.modules += len(outcome["rows"])


def build(
    version: str,
    *,
    force: bool = False,
    data_root: Path | None = None,
    git: str = "git",
    repo_urls: dict[str, str] | None = None,
    clone: Callable[[str, str, Path, str], str | None] = clone_repo,
    on_progress: Callable[[int, int, str, str | None], None] | None = None,
) -> BuildStats:
    """Build (or refresh) the OCA catalog for one Odoo version.

    *repo_urls* maps repo name → clone URL; when omitted, repos come from
    `enumerate_oca_repos` (GitHub API with a local fallback). *clone* and
    *on_progress* are injectable for tests and for progress reporting.
    Returns BuildStats; raises RuntimeError when no repo list can be found
    or when `git` is not on PATH. The per-repo worktrees are deleted after
    indexing -- the catalog, not the clone, is what's kept.
    """
    if not VERSION_RE.fullmatch(version):
        raise RuntimeError(f"invalid Odoo version {version!r}: expected e.g. 18.0")
    start = time.time()
    data_root = Path(data_root) if data_root else paths.data_dir() / "oca"
    data_root.mkdir(parents=True, exist_ok=True)
    stats = BuildStats(version=version)
    stats.db_path = str(_db_path(data_root, version))

    if not force and Path(stats.db_path).is_file():
        stats.already_built = True
        return stats

    # Make sure `git` exists before we start a 10-minute run that fails at
    # repo #12. Exception is FileNotFoundError when missing on PATH.
    probe = subprocess.run([git, "--version"], capture_output=True, text=True, timeout=60)
    if probe.returncode != 0:
        raise RuntimeError(
            f"`checkbox oca build` needs a git executable on PATH (`{git}` failed): "
            "searching a built index does not, building one does."
        )

    if repo_urls is None:
        names = enumerate_oca_repos(data_root)
        stats.repos_total = len(names)
        repo_urls = {name: REPO_BASE_URL.format(repo=name) for name in names}
    else:
        stats.repos_total = len(repo_urls)

    lock = _acquire_build_lock(data_root, version)
    partial = data_root / f".build-{version}.partial.jsonl"
    work = data_root / f".build-{version}"
    try:
        if force:
            partial.unlink(missing_ok=True)
        done = _load_partial(partial)
        if work.exists():
            _rmtree(work)
        work.mkdir(parents=True)

        rows: list[dict[str, Any]] = []
        todo: list[tuple[str, str]] = []
        for name, url in repo_urls.items():
            if name in NON_MODULE_REPOS:
                stats.repos_excluded += 1
            elif name in done:
                _count_outcome(stats, rows, done[name])  # resumed from a checkpoint
            else:
                todo.append((name, url))
        seen = stats.repos_excluded + stats.repos_indexed + stats.repos_no_branch

        def fetch(item: tuple[str, str]) -> tuple[str, Any]:
            name, url = item
            try:
                return name, clone(url, version, work / name, git)
            except (OSError, subprocess.TimeoutExpired) as exc:
                print(f"oca: repo {name} failed ({exc}) -- skipped", file=sys.stderr)
                return name, "error"

        with ThreadPoolExecutor(max_workers=BUILD_JOBS) as pool:
            for name, last_commit in pool.map(fetch, todo):
                seen += 1
                dest = work / name
                detail: str | None = None
                if last_commit is None:
                    outcome = {"repo": name, "status": "no_branch", "rows": []}
                elif last_commit == "error":
                    stats.repos_failed += 1  # not checkpointed: a rerun retries it
                    outcome = None
                else:
                    repo_rows = _index_worktree(dest, name, version, last_commit)
                    outcome = {"repo": name, "status": "indexed", "rows": repo_rows}
                    detail = f"{len(repo_rows)} modules"
                _rmtree(dest)
                if outcome is not None:
                    _count_outcome(stats, rows, outcome)
                    _append_partial(partial, outcome)
                if on_progress:
                    on_progress(seen, stats.repos_total, name, detail)
    finally:
        if work.exists():
            _rmtree(work)
        lock.unlink(missing_ok=True)

    write_catalog(
        Path(stats.db_path),
        rows,
        extra={
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "repos_indexed": str(stats.repos_indexed),
            "repos_no_branch": str(stats.repos_no_branch),
            "repos_failed": str(stats.repos_failed),
        },
    )
    partial.unlink(missing_ok=True)
    stats.elapsed_seconds = time.time() - start
    return stats


def catalog_status(data_root: Path | None = None) -> list[dict[str, str]]:
    """One row per built catalog: version, module count, built_at."""
    data_root = data_root or (paths.data_dir() / "oca")
    status: list[dict[str, str]] = []
    for version in built_versions(data_root):
        db = _db_path(data_root, version)
        con = sqlite3.connect(str(db))
        try:
            meta = dict(con.execute("SELECT k, v FROM meta").fetchall())
            count = con.execute("SELECT COUNT(*) FROM modules").fetchone()[0]
        except sqlite3.Error:
            status.append(
                {"version": version, "modules": "unreadable", "built_at": "", "db_path": str(db)}
            )
            continue
        finally:
            con.close()
        status.append(
            {
                "version": version,
                "modules": str(count),
                "built_at": meta.get("built_at", ""),
                "db_path": str(db),
            }
        )
    return status
