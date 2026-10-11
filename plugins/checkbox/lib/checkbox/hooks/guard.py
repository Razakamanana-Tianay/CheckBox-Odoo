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

from checkbox.card import _MODULE_NAME_RE


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
    target = Path(target).resolve()
    for addon_root in getattr(profile, "custom_addons", None) or []:
        if not addon_root:
            continue
        # `root / x` keeps an absolute x as is, and resolve() folds `./x`.
        try:
            rest = target.relative_to((Path(root) / addon_root).resolve()).parts
        except ValueError:
            continue
        # A file inside a module directory. With the repo root as an addons
        # root (`custom_addons: ["."]`), `.checkbox/` and `.git/` are not
        # modules; the name rule is the card's own (card._MODULE_NAME_RE).
        if len(rest) >= 2 and _MODULE_NAME_RE.match(rest[0]):
            return rest[0]
    return None
