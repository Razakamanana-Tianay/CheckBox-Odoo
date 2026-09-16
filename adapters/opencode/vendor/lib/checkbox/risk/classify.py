"""classify(path, profile) -> {tier, reasons}. docs/ARCHITECTURE.md §6.2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from checkbox.risk import pyscan, xmlscan
from checkbox.risk import rules as rules_mod

_TIER_ORDER = {"green": 0, "amber": 1, "red": 2}


def _highest_tier(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "green"
    return max((f["tier"] for f in findings), key=lambda t: _TIER_ORDER.get(t, 0))


def classify_file(path: Path, version: str) -> dict[str, Any]:
    """Classify one file. *version* selects the risk rule overlay
    (17.0/18.0/19.0) -- callers without a version yet should fall back to
    the most recent one they support rather than guessing; there's no
    version-agnostic rule set, model/method risk is inherently
    version-specific data."""
    path = Path(path)
    rules = rules_mod.load(version)
    if path.suffix == ".py":
        findings = pyscan.scan(path, rules)
    elif path.suffix in (".xml", ".csv"):
        findings = xmlscan.scan(path, rules)
    else:
        findings = []
    return {"tier": _highest_tier(findings), "reasons": findings}


def classify(path: Path, profile: Any) -> dict[str, Any]:
    """Classify *path* against *profile*'s Odoo version (a
    checkbox.profile.Profile, or anything with an `odoo_version` attribute)."""
    version = getattr(profile, "odoo_version", None) or "18.0"
    return classify_file(path, version)
