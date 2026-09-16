"""Project root and data-directory resolution. No I/O beyond the filesystem checks below."""

from __future__ import annotations

import os
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward from *start* (default: cwd) for a `.checkbox/` dir or a `.git` root.

    Falls back to *start* itself when neither marker is found, so callers
    always get a usable path instead of an exception -- a bare Odoo source
    checkout with no project state yet is a valid, expected input to
    `checkbox init`.
    """
    cur = (start or Path.cwd()).resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".checkbox").is_dir() or (candidate / ".git").exists():
            return candidate
    return cur


def data_dir() -> Path:
    """Resolve the checkbox data directory.

    Order: CHECKBOX_DATA_DIR env > CLAUDE_PLUGIN_DATA env > ~/.cache/checkbox.
    Matches docs/ARCHITECTURE.md §7.2 and the "Don't put runtime state in
    CLAUDE_PLUGIN_ROOT" rule in the repo's CLAUDE.md.
    """
    for var in ("CHECKBOX_DATA_DIR", "CLAUDE_PLUGIN_DATA"):
        val = os.environ.get(var)
        if val:
            return Path(val)
    return Path.home() / ".cache" / "checkbox"
