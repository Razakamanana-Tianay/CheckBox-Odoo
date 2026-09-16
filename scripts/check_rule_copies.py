#!/usr/bin/env python3
"""Fail if adapters/ has drifted from a fresh render of plugins/checkbox/rules/.

adapters/CLAUDE.md's own rule: every committed adapter file must match what
build_adapters.py would produce right now. build_adapters.build() renders
everything in memory (no filesystem writes), so the diff here is a plain
string comparison against the committed files -- no temp directory needed.

Exit codes: 0 no drift, 1 drift found (adapters/ is stale -- re-run
build_adapters.py and commit the result), 2 usage/environment error.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_adapters  # noqa: E402

REPO_ROOT = build_adapters.REPO_ROOT
ADAPTERS_DIR = REPO_ROOT / "adapters"


def main(argv: list[str] | None = None) -> int:
    if not ADAPTERS_DIR.is_dir():
        print(f"error: {ADAPTERS_DIR} does not exist", file=sys.stderr)
        return 2

    rendered = build_adapters.build()

    drifted: list[str] = []
    for rel_path, expected in rendered.items():
        committed_path = ADAPTERS_DIR / rel_path
        if not committed_path.is_file():
            drifted.append(f"{rel_path}: missing (never built, or deleted by hand)")
            continue
        actual = committed_path.read_text(encoding="utf-8")
        if actual != expected:
            drifted.append(f"{rel_path}: differs from a fresh render")

    # Catch stale files too: anything under adapters/ that build_adapters.py
    # no longer produces (a renderer was removed but the output wasn't).
    known_paths = {ADAPTERS_DIR / rel_path for rel_path in rendered}
    for path in ADAPTERS_DIR.rglob("*"):
        if path.is_file() and path.name != "CLAUDE.md" and path not in known_paths:
            drifted.append(f"{path.relative_to(ADAPTERS_DIR)}: stale, no renderer produces it")

    if drifted:
        print(f"adapters/ is stale ({len(drifted)} issue(s)):", file=sys.stderr)
        for issue in drifted:
            print(f"  - {issue}", file=sys.stderr)
        print(
            "\nRun: python3 scripts/build_adapters.py, then commit the result.",
            file=sys.stderr,
        )
        return 1

    print(f"ok: adapters/ matches a fresh render ({len(rendered)} file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
