"""SubagentStart hook: inject the compact ladder into subagents. `checkbox hook subagent-start`.

SessionStart context is parent-thread only and never reaches subagents
(verified against the hooks reference, corroborated by Ponytail's own
shipped comment to the same effect). Fires for every subagent by default --
scope it via hooks.json's own `matcher` field (a regex on agent_type, e.g.
"Explore") rather than an env-var workaround. The hooks reference
explains why the CHECKBOX_SUBAGENT_MATCHER env var this project's own
architecture doc originally proposed is unnecessary: the platform's native
matcher already does the same job declaratively.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from checkbox import ladder
from checkbox import mode as mode_mod
from checkbox.hooks.common import emit_hook_context, safe_main
from checkbox.profile import load as load_profile


def _run(payload: dict[str, Any]) -> None:
    root = Path(payload.get("cwd") or ".").resolve()
    resolved_mode = mode_mod.resolve(root)
    if resolved_mode not in ("full", "strict"):
        return
    try:
        profile = load_profile(root)
    except FileNotFoundError:
        return
    emit_hook_context("SubagentStart", ladder.render("lite", profile, mode=resolved_mode))


def main() -> int:
    return safe_main(_run)


if __name__ == "__main__":
    raise SystemExit(main())
