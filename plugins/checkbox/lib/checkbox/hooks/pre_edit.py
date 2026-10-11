"""PreToolUse guard on file edits. `checkbox hook pre-edit`.

§8.2 row: PreToolUse, matcher Write|Edit. Levels: full, strict.

- **every level:** deny any write to `.checkbox/approvals.json`.
- **strict:** also deny writes to `.checkbox/local.json` and `profile.json`
  (the two files that can switch this guard off).
- **strict:** deny an edit under `custom_addons` when no *approved* card
  lists that addon (permissionDecision "deny", reason names the fix).
- **full:** allow it, and inject a reminder when no approved card covers
  the addon.

Per the hook perf budget (§8.5: p95 ≤ 150 ms), this reads only the profile,
the approvals file and the approved card files -- never the evidence index.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from checkbox import approvals
from checkbox import mode as mode_mod
from checkbox.hooks import guard
from checkbox.hooks.common import (
    emit_deny,
    emit_hook_context,
    project_root,
    safe_main,
    tool_target,
)
from checkbox.profile import ProfileError
from checkbox.profile import load as load_profile

# Files the agent may not write (ARCHITECTURE §5.2; repo CLAUDE.md "Don't let
# the agent approve cards ... by any path"). approvals.json is human-only at
# every level, `off` included; the two files that can switch the guard off
# are protected only where there is a guard to switch off (strict).
_PROTECTED = {"local.json": ("strict",), "profile.json": ("strict",)}


def _protected_reason(target: Path, mode: str) -> str | None:
    if target.name == "approvals.json":
        return (
            ".checkbox/approvals.json is written only by a human running "
            "`checkbox approve <id>` in their own terminal (§5.2)."
        )
    if mode in _PROTECTED.get(target.name, ()):
        return (
            f"strict mode: .checkbox/{target.name} decides whether the guard applies, so "
            "only a human changes it, in their own terminal "
            "(`checkbox mode set <level>` / `checkbox profile write`)."
        )
    return None


def _run(payload: dict[str, Any]) -> None:
    target = tool_target(payload)
    if target is None:
        return
    # Checked before the mode gate, and before anything that reads project
    # files (a corrupt profile.json must not be a way around it):
    # approvals.json is human-only at every level.
    in_state_dir = target.parent.name == ".checkbox"
    if in_state_dir and target.name == "approvals.json":
        emit_deny("PreToolUse", _protected_reason(target, "off"))
        return
    root = project_root(payload, target)
    resolved_mode = mode_mod.resolve(root)
    if in_state_dir:
        reason = _protected_reason(target, resolved_mode)
        if reason:
            emit_deny("PreToolUse", reason)
        return
    if resolved_mode not in ("full", "strict"):
        return
    try:
        profile = load_profile(root)
    except FileNotFoundError:
        return  # no profile -> nothing is known to be a custom addon
    except ProfileError as exc:
        # Which files are custom addons is unknown, so nothing can be waved
        # through; the profile itself (under .checkbox/) stays editable above.
        emit_deny(
            "PreToolUse",
            f"checkbox: {exc}. Fix .checkbox/profile.json (or re-run /checkbox:init) "
            "before editing project files; `checkbox mode set off` in your own terminal "
            "turns the policy off.",
        )
        return
    addon = guard.addon_for_path(root, profile, target)
    if addon is None:
        return
    covers = approvals.covers_addon(root, addon)
    if covers:
        return
    if resolved_mode == "strict":
        emit_deny(
            "PreToolUse",
            f"strict mode: no approved card authorizes changes in addon '{addon}'. "
            f"Walk the ladder and draft a card with `checkbox card next-id`, then a human "
            f"must approve it with `checkbox approve <id>` in their own terminal.",
        )
    else:
        emit_hook_context(
            "PreToolUse",
            f"checkbox: no approved card covers addon '{addon}'. In full mode this is "
            "allowed, but a card is expected before the change is considered done.",
        )


def main() -> int:
    return safe_main(_run)


if __name__ == "__main__":
    raise SystemExit(main())
