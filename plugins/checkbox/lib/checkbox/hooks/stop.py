"""Stop hook. `checkbox hook stop`.

§8.2 row: Stop. Levels: full, strict. When addon files were edited in this
session and a touched module has no card (full: any live card listing it;
strict: an approved one), block stopping once with the reason "decision card
missing". Exiting 2 blocks the turn end.

Loop protection, both verified against code.claude.com/docs/en/hooks
(Stop section, 2026-10-11): the payload's `stop_hook_active` is "true when
Claude Code is already continuing as a result of a stop hook", so a stop
that follows our own block is always let through; and the session state's
stop-block counter keeps it to one block per session, since in full mode
the agent cannot produce an approval however often it is asked.

The reason goes to **stderr**, not stdout: "The blocking message is the
reason from your JSON's blocking decision when it makes one, and your
stderr text otherwise" (same page, 2026-09-15).
"""

from __future__ import annotations

import sys
from typing import Any

from checkbox import approvals
from checkbox import mode as mode_mod
from checkbox import session as session_mod
from checkbox.hooks.common import project_root, safe_main


def _run(payload: dict[str, Any]) -> int | None:
    root = project_root(payload)
    resolved_mode = mode_mod.resolve(root)
    if resolved_mode not in ("full", "strict"):
        return 0
    if payload.get("stop_hook_active"):
        return 0
    session_id = str(payload.get("session_id") or "unknown")
    state = session_mod.load(root, session_id)
    touched = [a for a in state.get("touched_addons", []) if a]
    has_card = approvals.covers_addon if resolved_mode == "strict" else approvals.lists_addon
    uncovered = sorted(a for a in touched if not has_card(root, a))
    under_tiered = []
    for addon, tier in sorted((state.get("classified_tiers") or {}).items()):
        declared = approvals.declared_tier(root, addon)
        if declared and approvals.TIER_ORDER.get(tier, 0) > approvals.TIER_ORDER[declared[1]]:
            under_tiered.append(f"{addon} (card {declared[0]}: {declared[1]}, code: {tier})")
    if not uncovered and not under_tiered:
        return 0
    if int(state.get("stop_block_count", 0)) > 0:
        return 0  # already blocked once this session; don't loop
    session_mod.increment_stop_block_count(root, session_id)
    parts = []
    if uncovered:
        parts.append(
            f"addon files were edited this session ({', '.join(uncovered)}) and no "
            + ("approved " if resolved_mode == "strict" else "")
            + "decision card lists them. Walk the ladder and draft a card with "
            "`checkbox card next-id`; a human approves it with `checkbox approve <id>`."
        )
    if under_tiered:
        parts.append(
            "the code classifies above its card's tier: "
            + "; ".join(under_tiered)
            + ". Raise the card's tier to match (that voids its approval)."
        )
    sys.stderr.write(
        "checkbox: stopping blocked once -- "
        + " Also, ".join(parts)
        + " Run /checkbox:mode if you intend to disable this."
    )
    return 2


def main() -> int:
    return safe_main(_run)


if __name__ == "__main__":
    raise SystemExit(main())
