"""PreToolUse guard on file edits. `checkbox hook pre-edit`.

§8.2 row: PreToolUse, matcher Write|Edit. Levels: full, strict.

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
from checkbox.hooks.common import emit_deny, emit_hook_context, safe_main
from checkbox.profile import load as load_profile


def _run(payload: dict[str, Any]) -> None:
    root = Path(payload.get("cwd") or ".").resolve()
    resolved_mode = mode_mod.resolve(root)
    if resolved_mode not in ("full", "strict"):
        return
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path:
        return
    target = Path(file_path)
    if not target.is_absolute():
        target = root / target
    try:
        profile = load_profile(root)
    except FileNotFoundError:
        return  # no profile -> nothing is known to be a custom addon
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
