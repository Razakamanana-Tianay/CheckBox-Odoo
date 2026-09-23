"""Unified search: builds (or reuses) the source index, then queries it.

docs.py (odoo/documentation -- network clones) is still deferred past this
pass: its only consumer is a card's `evidence` field and, unlike OCA, there
is no named need for it yet. `search()` accepts `kinds` already scoped to
what exists ("source", plus "oca" since the OCA catalog landed) plus the
values ARCHITECTURE.md §7 reserves for later so callers don't need to change
when docs/live land.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from checkbox import paths
from checkbox.knowledge import oca as oca_mod
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
    all_versions: bool = False,
) -> list[dict[str, Any]]:
    """Evidence across the built indexes.

    `kinds=None` means every built kind: source (always) and oca (when a
    catalog exists for the profile's version). Source hits come from the
    FTS5/LIKE index; OCA hits from the per-version catalog ranker
    (`knowledge/oca.py`), which is keyword-based and deterministic. With
    *all_versions* the OCA search spans every built catalog and each result
    keeps its real branch in `version` so version-only availability is an
    explicit fact ("exists on 17.0, not on 18.0").
    """
    source_hits: list[dict[str, Any]] = []
    oca_hits: list[dict[str, Any]] = []
    if not kinds or "source" in kinds:
        db_path = ensure_index(profile, project_root)
        con = store.connect(db_path)
        try:
            source_hits = store.search(con, query, limit=limit)
        finally:
            con.close()
    oca_data = paths.data_dir() / "oca"
    if not kinds or "oca" in kinds:
        version = profile.odoo_version
        if all_versions:
            oca_hits = oca_mod.search_all_versions(query, oca_data, limit=limit)
        elif version:
            db = oca_data / f"{version}.sqlite"
            if db.is_file():
                oca_hits = oca_mod.search_catalog(query, db, limit=limit)
    # Scores from the two rankers are on different scales, so they are never
    # compared: each kind keeps its own order and the merge alternates, so
    # `limit` bounds the total and neither kind starves the other.
    results: list[dict[str, Any]] = []
    for i in range(max(len(source_hits), len(oca_hits))):
        results.extend(hits[i] for hits in (source_hits, oca_hits) if i < len(hits))
    if kinds:
        results = [r for r in results if r["kind"] in kinds]
    return results[:limit]
