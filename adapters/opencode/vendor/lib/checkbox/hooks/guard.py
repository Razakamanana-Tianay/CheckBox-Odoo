"""Shared guard logic for the four P4 guard hooks.

Resolving "which addon is this file in, if any" is the one piece of real
domain logic the guards share (pre-edit's denial scope, post-edit's touched-
addon recording, stop's coverage check). Everything else -- mode gating,
payload parsing -- stays in each hook so a guard can be understood on its
own. Imported only by hooks; never by the CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def addon_for_path(root: Path, profile: Any, target: Path) -> str | None:
    """Return the addon name *target* belongs to when it sits under one of
    the profile's `custom_addons` roots (relative to *root*), else None.

    `custom_addons` entries are directories of modules (Appendix B), so the
    addon is the path segment right after the addon root: an edit to
    `addons/mymodule/models/x.py` with `custom_addons: ["addons"]` belongs
    to `mymodule`. A target outside every custom addon root (one of Odoo's
    own bundled addons, enterprise, third-party) is out of scope for every
    P4 guard and returns None.
    """
    try:
        rel = Path(target).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return None
    for addon_root in getattr(profile, "custom_addons", None) or []:
        parts = Path(addon_root).parts
        if not parts or rel.parts[: len(parts)] != parts:
            continue
        rest = rel.parts[len(parts) :]
        if rest and rest[0]:
            return rest[0]
    return None
