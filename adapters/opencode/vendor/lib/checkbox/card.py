"""Decision cards: parse, validate, and number them.

Format is docs/ARCHITECTURE.md §5.1: a Markdown file with one fenced
` ```checkbox-card ` block of `key: value` lines around free-text prose.
Validation rules are lib/checkbox/CLAUDE.md's "Contracts" section, which is
the operational (and simpler) restatement of §5.1/§5.2 this module actually
implements -- notably it requires `tier` for verdicts `code` and `module`
only, not ARCHITECTURE.md §5.1's harder-to-check "nocode with Python"
condition, which would need parsing free-text `steps` for Python mentions.
That's out of scope here; a human sets `tier` by hand on a Python-bearing
nocode card if one comes up.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

FENCE_LANG = "checkbox-card"
VALID_VERDICTS = ("skip", "standard", "config", "nocode", "module", "code")
VALID_TIERS = ("-", "green", "amber", "red")
VALID_STATUSES = ("proposed", "approved", "rejected", "superseded")
_EVIDENCE_KINDS = ("source", "docs", "oca", "live", "unverified")
_TIER_REQUIRED_VERDICTS = ("code", "module")
_EVIDENCE_REQUIRED_VERDICTS = ("standard", "config", "module")

_FENCE_RE = re.compile(rf"```{FENCE_LANG}\n(.*?)```", re.DOTALL)
_KEY_LINE_RE = re.compile(r"^([a-z_]+):\s*(.*)$")

# Best-effort PII lint (repo CLAUDE.md §5.1: "a best-effort PII lint rejects
# emails, IBANs and VAT-like tokens"). These are deliberately loose -- a
# false positive just makes a human re-word a line, a false negative leaks
# nothing extra since the lint is a courtesy check, not the only defense.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_VAT_RE = re.compile(r"\b[A-Z]{2}\d{8,12}\b")


def parse(text: str) -> dict[str, Any]:
    """Parse a card file's fenced block into a flat dict of its raw string fields.

    Raises ValueError if no `checkbox-card` fence is found -- a card file
    without one isn't a parsing edge case, it's not a card.
    """
    match = _FENCE_RE.search(text)
    if not match:
        raise ValueError(f"no ```{FENCE_LANG} fenced block found")
    fields: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        key_match = _KEY_LINE_RE.match(line)
        if not key_match:
            continue  # tolerate stray lines rather than crashing on a hand-edited card
        fields[key_match.group(1)] = key_match.group(2).strip()
    fields["evidence"] = _parse_evidence(fields.get("evidence", ""))
    fields["addons"] = _parse_list(fields.get("addons", ""))
    return fields


def _parse_evidence(raw: str) -> list[dict[str, str]]:
    if not raw or raw == "-":
        return []
    items = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        kind, _, ref = chunk.partition("|")
        items.append({"kind": kind.strip(), "ref": ref.strip()})
    return items


def _parse_list(raw: str) -> list[str]:
    if not raw or raw == "-":
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def next_id(directory: Path) -> str:
    """Return the next zero-padded 4-digit card id for *directory* (`.checkbox/decisions/`)."""
    directory = Path(directory)
    if not directory.is_dir():
        return "0001"
    highest = 0
    for path in directory.glob("[0-9][0-9][0-9][0-9]-*.md"):
        try:
            highest = max(highest, int(path.name[:4]))
        except ValueError:
            continue
    return f"{highest + 1:04d}"


def lint_pii(text: str) -> list[str]:
    """Return a list of warnings for lines that look like they carry client PII."""
    warnings: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _EMAIL_RE.search(line):
            warnings.append(f"line {lineno}: looks like an email address")
        elif _IBAN_RE.search(line) or _VAT_RE.search(line):
            warnings.append(f"line {lineno}: looks like an IBAN or VAT number")
    return warnings


def validate(
    card: dict[str, Any],
    profile: Any = None,
    approvals: dict[str, Any] | None = None,
    raw_text: str = "",
) -> list[str]:
    """Return a list of error strings; empty means valid.

    *profile* (a checkbox.profile.Profile, optional) is used only to check
    `addons` against `custom_addons` when the verdict is `code`. *approvals*
    is accepted for the caller's convenience but not yet used -- approval
    revalidation (hash-matches-approved-block) belongs to approvals.py, not
    here; this only validates the card's own internal consistency.
    """
    errors: list[str] = []

    verdict = card.get("verdict")
    if verdict not in VALID_VERDICTS:
        errors.append(f"verdict must be one of {VALID_VERDICTS}, got {verdict!r}")

    status = card.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"status must be one of {VALID_STATUSES}, got {status!r}")

    tier = card.get("tier", "-")
    if tier not in VALID_TIERS:
        errors.append(f"tier must be one of {VALID_TIERS}, got {tier!r}")
    elif verdict in _TIER_REQUIRED_VERDICTS and tier == "-":
        errors.append(f"tier is required when verdict is {verdict!r}")

    evidence = card.get("evidence", [])
    if verdict in _EVIDENCE_REQUIRED_VERDICTS:
        non_unverified = [e for e in evidence if e.get("kind") != "unverified"]
        if not non_unverified:
            errors.append(
                f"verdict {verdict!r} needs at least one evidence item that isn't 'unverified'"
            )
    for item in evidence:
        if item.get("kind") not in _EVIDENCE_KINDS:
            errors.append(
                f"evidence kind must be one of {_EVIDENCE_KINDS}, got {item.get('kind')!r}"
            )

    if verdict == "code" and profile is not None:
        custom_addons = set(getattr(profile, "custom_addons", []) or [])
        for addon in card.get("addons", []):
            if addon not in custom_addons:
                allowed = sorted(custom_addons)
                errors.append(f"addons entry {addon!r} is not in custom_addons {allowed}")

    if status == "proposed" and "id" not in card:
        errors.append("card is missing 'id'")

    if raw_text:
        pii = lint_pii(raw_text)
        errors.extend(f"possible PII: {w}" for w in pii)

    return errors
