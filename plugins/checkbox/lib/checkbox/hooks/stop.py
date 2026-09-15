"""Stop hook. `checkbox hook stop`.

§8.2 row: Stop. Levels: full, strict. When addon files were edited in this
session and no approved card covers a touched addon, block stopping once
with the reason "decision card missing". Exiting 2 blocks the turn end
(verified against the hooks reference); the block-once behaviour is built
on the session state's stop-block counter because no stop-active flag
exists in the platform.

The reason goes to **stderr**, not stdout: verified against
code.claude.com/docs/en/hooks, 2026-09-15 -- "The blocking message is the
reason from your JSON's blocking decision when it makes one, and your
stderr text otherwise." Stop emits no JSON decision here (there's no
documented hookSpecificOutput shape for Stop the way PreToolUse has
permissionDecision), so stderr is the only path the message reaches Claude
through; stdout would be logged to the debug log and never surfaced.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from checkbox import approvals
from checkbox import mode as mode_mod
from checkbox import session as session_mod
from checkbox.hooks.common import safe_main


def _run(payload: dict[str, Any]) -> int | None:
    root = Path(payload.get("cwd") or ".").resolve()
    resolved_mode = mode_mod.resolve(root)
    if resolved_mode not in ("full", "strict"):
        return 0
    session_id = str(payload.get("session_id") or "unknown")
    state = session_mod.load(root, session_id)
    touched = [a for a in state.get("touched_addons", []) if a]
    if not touched:
        return 0
    uncovered = [a for a in touched if not approvals.covers_addon(root, a)]
    if not uncovered:
        return 0
    if int(state.get("stop_block_count", 0)) > 0:
        return 0  # already blocked once this session; don't loop
    session_mod.increment_stop_block_count(root, session_id)
    sys.stderr.write(
        "checkbox: stopping blocked once -- addon files were edited this session "
        + f"({', '.join(sorted(uncovered))}) and no approved card covers them. "
        + "Walk the ladder and draft a card with `checkbox card next-id`; a human "
        + "approves it with `checkbox approve <id>`. Run /checkbox:mode if you "
        + "intend to disable this."
    )
    return 2


def main() -> int:
    return safe_main(_run)


if __name__ == "__main__":
    raise SystemExit(main())
