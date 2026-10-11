"""PostToolUse on file edits. `checkbox hook post-edit`.

§8.2 row: PostToolUse, matcher Write|Edit. Levels: full, strict. Classifies
the just-edited file against its version's risk rules and injects the tier
and reasons as context; records the touched addon in session state so the
Stop hook can block when the session ends without a card covering it.

Classifying a single file is well under the hook perf budget (§8.5); the
evidence index is never opened.
"""

from __future__ import annotations

from typing import Any

from checkbox import mode as mode_mod
from checkbox import session as session_mod
from checkbox.hooks import guard
from checkbox.hooks.common import emit_hook_context, project_root, safe_main, tool_target
from checkbox.profile import ProfileError
from checkbox.profile import load as load_profile
from checkbox.risk import classify as classify_mod


def _run(payload: dict[str, Any]) -> None:
    root = project_root(payload, tool_target(payload))
    resolved_mode = mode_mod.resolve(root)
    if resolved_mode not in ("full", "strict"):
        return
    target = tool_target(payload)
    if target is None:
        return
    profile = None
    try:
        profile = load_profile(root)
    except (FileNotFoundError, ProfileError):
        return
    addon = guard.addon_for_path(root, profile, target)
    session_id = payload.get("session_id") or "unknown"
    if addon:
        session_mod.record_touched_addon(root, str(session_id), addon)

    try:
        result = classify_mod.classify_file(target, profile.odoo_version or "18.0")
    except FileNotFoundError:
        return
    findings = result.get("reasons") or []
    if not findings:
        return
    lines = [f"checkbox risk: {target.name} is {result['tier'].upper()} tier"]
    for finding in findings[:6]:
        loc = f":{finding['line']}" if finding.get("line") else ""
        lines.append(f"  {finding['rule_id']}{loc} -- {finding['detail']}")
    if result["tier"] == "red":
        lines.append(
            "red change: a human must read every line, a ledger-reviewer "
            "report is required, and the card needs human approval before merge (§6.1)"
        )
    emit_hook_context("PostToolUse", "\n".join(lines))


def main() -> int:
    return safe_main(_run)


if __name__ == "__main__":
    raise SystemExit(main())
