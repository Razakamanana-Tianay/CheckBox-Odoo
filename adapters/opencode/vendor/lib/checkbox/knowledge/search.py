"""Unified search: builds (or reuses) the source index, then queries it.

docs.py and oca.py (odoo/documentation and curated OCA repos -- network
clones) are deferred past this pass: their only consumer is a card's
`evidence` field, not this module's own contract, and they need network
access this environment has to spend carefully (~4.6GB free disk when this
was written). `search()` accepts `kinds` already scoped to what exists
("source") plus the values ARCHITECTURE.md §7 reserves for later so callers
don't need to change when docs/oca land.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from checkbox import paths
from checkbox.knowledge import source as source_mod
from checkbox.knowledge import store
from checkbox.profile import Profile, resolve_addon_roots


def _index_path(roots: list[Path], version: str) -> Path:
    key = f"{version}|" + "|".join(sorted(str(r) for r in roots))
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return paths.data_dir() / "source" / f"{digest}.sqlite"


def _newest_mtime(roots: list[Path]) -> float:
    """Latest mtime of any file under *roots* that `source.build()` would
    actually read -- 0.0 if none exist.

    Cached indexes never expired on their own (caught while building P5's
    eval fixtures: adding a settings view *after* the first `checkbox
    search` call left it permanently unindexed, silently, since `.sqlite`
    existing was the only staleness check). This runs on *every* search
    call, not just index builds -- `ensure_index` isn't hook-gated
    (lib/checkbox/CLAUDE.md: hooks never touch `knowledge/`), so it's not
    bound by the 150ms hook budget, but a real checkout's `i18n/`/`static/`
    directories alone can be most of its files, so walking them on every
    call for a staleness check that never reads them is pure waste --
    measured 17x slower on a synthetic tree shaped like a real addon set.
    `source.iter_relevant_files` prunes the same NOISE_DIRS `build()`
    itself skips, which also keeps the two walks in sync by construction.
    """
    newest = 0.0
    for root in roots:
        if not root.is_dir():
            continue
        for path in source_mod.iter_relevant_files(root):
            mtime = path.stat().st_mtime
            if mtime > newest:
                newest = mtime
    return newest


def ensure_index(profile: Profile, project_root: Path, *, force: bool = False) -> Path:
    """Build the source index for *profile* if it doesn't exist yet, is
    stale (some file under an addon root is newer than the index), or
    *force* is set. Returns the index path either way."""
    roots = resolve_addon_roots(profile, project_root)
    version = profile.odoo_version or "unknown"
    db_path = _index_path(roots, version)
    stale = db_path.is_file() and _newest_mtime(roots) > db_path.stat().st_mtime
    if db_path.is_file() and not force and not stale:
        return db_path
    docs = source_mod.build(roots, version)
    con = store.connect(db_path)
    store.clear(con)
    store.index_documents(con, docs)
    con.close()
    return db_path


def search(
    profile: Profile,
    project_root: Path,
    query: str,
    kinds: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    db_path = ensure_index(profile, project_root)
    con = store.connect(db_path)
    try:
        results = store.search(con, query, limit=limit)
    finally:
        con.close()
    if kinds:
        results = [r for r in results if r["kind"] in kinds]
    return results
