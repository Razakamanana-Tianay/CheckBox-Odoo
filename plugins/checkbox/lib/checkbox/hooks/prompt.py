"""UserPromptSubmit hook: per-turn compact ladder reminder. `checkbox hook prompt`.

Fires only in full/strict (docs/ARCHITECTURE.md §8.2's Levels column for
this row is "full, strict" -- lite already gets the compact ladder once, at
SessionStart; repeating it every turn would double the cost with no
documented benefit). Kept per docs/notes/platform-facts.md's Ponytail-
derived note: the per-turn reminder is a hypothesis pending P5 eval
evidence, not proven necessary -- don't remove it without that evidence,
and don't expand its scope either.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from checkbox import ladder
from checkbox import mode as mode_mod
from checkbox.hooks.common import emit_context, safe_main
from checkbox.profile import load as load_profile


def _run(payload: dict[str, Any]) -> None:
    root = Path(payload.get("cwd") or ".").resolve()
    resolved_mode = mode_mod.resolve(root)
    if resolved_mode not in ("full", "strict"):
        return
    try:
        profile = load_profile(root)
    except FileNotFoundError:
        return  # SessionStart already said the profile is missing, once
    emit_context(ladder.render("lite", profile, mode=resolved_mode))


def main() -> int:
    return safe_main(_run)


if __name__ == "__main__":
    raise SystemExit(main())
