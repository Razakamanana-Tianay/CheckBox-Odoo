"""SessionStart hook: inject the ladder + profile summary. `checkbox hook session-start`."""

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
    if resolved_mode == "off":
        return
    try:
        profile = load_profile(root)
    except FileNotFoundError:
        emit_context(
            "checkbox: no project profile yet at .checkbox/profile.json. "
            "This project uses a fit-gap policy for Odoo changes once one exists; "
            "run /checkbox:init to detect and confirm it.\n"
        )
        return
    emit_context(ladder.render(resolved_mode, profile) + "\n")


def main() -> int:
    return safe_main(_run)


if __name__ == "__main__":
    raise SystemExit(main())
