"""Render the ladder text from rules/ladder.md and ladder.compact.md.

Both files are the single source of truth (repo CLAUDE.md non-negotiable
#7): this module only fills placeholders, it never restates the ladder's
own wording inline.

Level semantics (not fully specified in ARCHITECTURE.md as written -- this
fills that gap with the smallest honest choice, per non-negotiable #8):
  - "off": caller emits nothing; render() is not even called.
  - "lite": ladder.compact.md, for a low-friction per-turn nudge.
  - "full", "strict": ladder.md in full. The *rendered text* is identical
    for both -- it never claimed anything about enforcement, so there was
    never anything to correct there. What differs is real, out-of-band
    behaviour: as of P4, hooks/pre_edit.py and hooks/pre_bash.py actually
    deny in strict (PreToolUse `permissionDecision: deny`) and only remind
    in full. That split lives entirely in the guard hooks, deliberately
    not duplicated into this text -- the deny reason the agent sees when it
    actually happens is more concrete and more current than any summary
    the ladder could carry, and the rules/CLAUDE.md placeholder contract
    ("an unknown placeholder is a test failure") is a reason to keep this
    template's placeholder set exactly as documented, not a reason to work
    around it.
"""

from __future__ import annotations

from pathlib import Path

from checkbox.profile import Profile

_RULES_DIR = Path(__file__).resolve().parent.parent.parent / "rules"


def _hosting_clause(profile: Profile) -> str:
    if profile.hosting == "online":
        return (
            "This database is on Odoo Online: custom Python modules cannot be installed, "
            "so rung 6 is not available; a remaining gap is reported on the card."
        )
    return ""


def _studio_clause(profile: Profile) -> str:
    return ", Studio" if profile.edition == "enterprise" else ""


def _profile_line(profile: Profile) -> str:
    if not profile.odoo_version:
        return "not detected yet -- run /checkbox:init"
    edition = profile.edition or "unknown edition"
    hosting = profile.hosting or "unknown hosting"
    return f"{profile.odoo_version} / {edition} / {hosting}"


def _placeholders(profile: Profile, mode: str) -> dict[str, str]:
    return {
        "profile_line": _profile_line(profile),
        "mode": mode,
        "version": profile.odoo_version or "an undetected version",
        "edition": profile.edition or "an undetected edition",
        "studio_clause": _studio_clause(profile),
        "hosting_clause": _hosting_clause(profile),
    }


def render(level: str, profile: Profile, *, mode: str | None = None) -> str:
    """Render the ladder for *level* ("lite" | "full" | "strict") against *profile*.

    *level* only selects which file to render (ladder.compact.md for
    "lite", ladder.md otherwise). The text's own "Policy level: {mode}"
    line is filled from *mode* if given, else from *level* -- callers that
    render the compact file for a full/strict per-turn reminder (prompt.py,
    subagent_start.py both pass level="lite" to pick the short template
    while the real policy mode is full/strict) must pass the real mode
    explicitly, or the ladder would claim to be in lite policy while a
    full/strict session is actually running.

    "off" is the caller's job to skip; calling render("off", ...) is a
    programming error, not a supported no-op, so it raises rather than
    silently returning an empty string.
    """
    if level == "off":
        raise ValueError("render('off', ...) is invalid; the caller must skip rendering entirely")
    filename = "ladder.compact.md" if level == "lite" else "ladder.md"
    template = (_RULES_DIR / filename).read_text(encoding="utf-8")
    return template.format(**_placeholders(profile, mode or level)).rstrip("\n")
