"""Profile: version, edition, hosting and addon paths for one Odoo project.

Schema is docs/ARCHITECTURE.md Appendix B. `detect()` only fills in what is
mechanically verifiable from the filesystem (version, edition, the addon
roots that exist); it never guesses which of those roots hold *custom* code
versus Odoo's own bundled addons -- that split needs a human, which is why
the `init` skill (P2) confirms it interactively rather than `detect()`
asserting it silently. This keeps non-negotiable #2 (deterministic first,
no LLM judgment where plain code can decide) honest: `detect()` reports
evidence, it does not decide `custom_addons`.
"""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
VALID_EDITIONS = ("community", "enterprise")
VALID_HOSTING = ("online", "odoo-sh", "on-premise")
VALID_MODES = ("off", "lite", "full", "strict")


@dataclass
class Profile:
    schema: int = SCHEMA_VERSION
    odoo_version: str | None = None
    edition: str | None = None
    hosting: str | None = None
    localizations: list[str] = field(default_factory=list)
    odoo_source: str | None = None
    enterprise_source: str | None = None
    custom_addons: list[str] = field(default_factory=list)
    third_party_addons: list[str] = field(default_factory=list)
    mode: str = "full"
    detected: dict[str, str] = field(default_factory=dict)
    confirmed_by_user: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _profile_path(root: Path) -> Path:
    return root / ".checkbox" / "profile.json"


def _resolve_release_py(root: Path) -> Path | None:
    """Return the first existing candidate location for Odoo's `odoo/release.py`.

    Every candidate follows the same shape, `<checkout_root>/odoo/release.py`
    -- `_parse_version_info`'s caller derives `odoo_source` as
    `release_py.parent.parent`, which only equals the checkout root under
    that shape. Appendix B's sibling-checkout example, `"odoo_source":
    "../odoo"`, names the sibling directory "odoo" and treats it as a full
    checkout, not as the inner package folder -- so the sibling candidate
    needs `odoo` twice (the checkout dir's own name, then its `odoo/`
    package), not once. A first version of this function had only one
    `odoo` segment here, which silently resolved `odoo_source` to the
    checkout's *parent* instead of the checkout itself; caught by
    tests/test_profile.py::test_detect_sibling_checkout_layout before P3
    could build an index against the wrong path.
    """
    candidates = [
        root / "odoo" / "release.py",  # root is (or vendors) the Odoo source checkout
        root / "release.py",  # root is the `odoo/` package dir itself
        root.parent / "odoo" / "odoo" / "release.py",  # sibling checkout named "odoo", Appendix B
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _parse_version_info(release_py: Path) -> tuple | None:
    """Extract Odoo's `version_info` tuple from a real `odoo/release.py`.

    Can't use `ast.literal_eval` on the tuple directly: real release.py
    files write it as `version_info = (18, 0, 0, FINAL, 0, '')`, where
    FINAL is a *name*, not a string literal (verified against
    raw.githubusercontent.com/odoo/odoo/18.0/odoo/release.py, 2026-09-15).
    So this resolves any Name reference against every simple
    `NAME = "literal"` assignment (or `A = [N1, N2] = ["v1", "v2"]`
    chained/unpacking assignment, the exact shape RELEASE_LEVELS uses)
    found elsewhere in the same module, instead of hard-coding
    RELEASE_LEVELS/ALPHA/BETA/etc. by name -- that keeps it working even if
    a future Odoo release renames those constants.
    """
    tree = ast.parse(release_py.read_text(encoding="utf-8"))
    name_map: dict[str, str] = {}
    version_info_node: ast.Tuple | ast.List | None = None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        # Simple `NAME = "literal"` -> record for later Name resolution.
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            name_map[node.targets[0].id] = node.value.value
        # Chained unpack `A = [N1, N2, ...] = ["v1", "v2", ...]`.
        for target in node.targets:
            if isinstance(target, (ast.List, ast.Tuple)) and isinstance(
                node.value, (ast.List, ast.Tuple)
            ):
                names = [e.id for e in target.elts if isinstance(e, ast.Name)]
                values = [
                    e.value
                    for e in node.value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)
                ]
                if len(names) == len(values):
                    name_map.update(dict(zip(names, values)))
        # The tuple we actually want.
        if len(node.targets) == 1 and getattr(node.targets[0], "id", None) == "version_info":
            if isinstance(node.value, (ast.Tuple, ast.List)):
                version_info_node = node.value

    if version_info_node is None:
        return None

    resolved = []
    for elt in version_info_node.elts:
        if isinstance(elt, ast.Constant):
            resolved.append(elt.value)
        elif isinstance(elt, ast.Name):
            resolved.append(name_map.get(elt.id, elt.id))
        else:
            resolved.append(None)
    return tuple(resolved)


def _find_web_enterprise(root: Path) -> Path | None:
    """Look for `web_enterprise/__manifest__.py`, the Enterprise-only signal.

    web_enterprise is confirmed absent from the Community monorepo (404 at
    raw.githubusercontent.com/odoo/odoo/18.0/addons/web_enterprise/, checked
    2026-09-15) and confirmed as a real Enterprise addon technical name by
    multiple odoo.com/forum threads about activating Enterprise. Checked
    against a small set of real-world candidate locations rather than an
    unbounded walk, since this runs from `checkbox init`/`detect`, not a hook.
    """
    candidates = [
        root / "web_enterprise",
        root / "enterprise" / "web_enterprise",
        root / "addons" / "web_enterprise",
        root / "odoo" / "addons" / "web_enterprise",
        root.parent / "enterprise" / "web_enterprise",
    ]
    for candidate in candidates:
        manifest = candidate / "__manifest__.py"
        if manifest.is_file():
            return candidate
    return None


def find_addon_roots(root: Path) -> list[str]:
    """Return, relative to *root*, every directory whose children include an
    installable-module directory (one holding `__manifest__.py`).

    Public (not `_`-prefixed) because knowledge/source.py (P3) reuses this
    to enumerate addon roots inside `odoo_source` for indexing, instead of
    re-deriving the same candidate list.
    """
    candidates = [
        root,
        root / "odoo" / "addons",
        root / "addons",
        root / "enterprise",
        root / "custom_addons",
    ]
    found: list[str] = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        try:
            has_module = any(
                (child / "__manifest__.py").is_file()
                for child in candidate.iterdir()
                if child.is_dir()
            )
        except OSError:
            continue
        if has_module:
            try:
                found.append(str(candidate.relative_to(root)) or ".")
            except ValueError:
                found.append(str(candidate))
    return found


def detect(root: Path) -> Profile:
    """Best-effort, source-grounded detection. Never raises on a bare/partial tree."""
    root = Path(root).resolve()
    profile = Profile()
    detected: dict[str, str] = {}

    release_py = _resolve_release_py(root)
    if release_py is not None:
        version_info = _parse_version_info(release_py)
        if version_info and len(version_info) >= 2:
            profile.odoo_version = f"{version_info[0]}.{version_info[1]}"
            profile.odoo_source = str(release_py.parent.parent)
            detected["odoo_version"] = f"source: {release_py}"

    web_enterprise = _find_web_enterprise(root)
    if web_enterprise is not None:
        profile.edition = "enterprise"
        profile.enterprise_source = str(web_enterprise.parent)
        detected["edition"] = f"web_enterprise found at {web_enterprise}"
    elif profile.odoo_version is not None:
        # Only assert "community" when we actually found an Odoo source to
        # check; otherwise this is silence, not evidence, per non-negotiable #3.
        profile.edition = "community"
        detected["edition"] = "no web_enterprise in the checked addon paths"

    addon_roots = find_addon_roots(root)
    if addon_roots:
        detected["addon_paths"] = ", ".join(addon_roots)

    profile.detected = detected
    return profile


def load(root: Path) -> Profile:
    path = _profile_path(Path(root))
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {f for f in Profile.__dataclass_fields__}
    return Profile(**{k: v for k, v in data.items() if k in known})


def load_file(path: Path) -> Profile:
    """Load a profile from an arbitrary JSON file, not the `.checkbox/profile.json`
    convention `load()` assumes -- for `checkbox search --profile <file>`,
    matching the CLI usage documented in the repo's CLAUDE.md."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    known = {f for f in Profile.__dataclass_fields__}
    return Profile(**{k: v for k, v in data.items() if k in known})


def resolve_addon_roots(profile: Profile, project_root: Path) -> list[Path]:
    """Absolute addon-root directories for *profile*: Odoo's own bundled
    addons (under `odoo_source`), Enterprise's (under `enterprise_source`),
    and the project's own custom/third-party addons (relative to
    *project_root*, per Appendix B -- a different base than `odoo_source`).
    """
    roots: list[Path] = []
    if profile.odoo_source:
        base = Path(profile.odoo_source)
        for rel in find_addon_roots(base):
            if rel in (".", "custom_addons"):
                continue  # checkout root itself, or a dir outside Odoo's own layout
            roots.append(base / rel)
    if profile.enterprise_source:
        roots.append(Path(profile.enterprise_source))
    for rel in (*profile.custom_addons, *profile.third_party_addons):
        roots.append(Path(project_root) / rel)
    return roots


def write(root: Path, profile: Profile) -> Path:
    path = _profile_path(Path(root))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(profile.to_dict(), indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    return path


def validate(profile: Profile) -> list[str]:
    """Return a list of error strings; empty means valid."""
    errors: list[str] = []
    if profile.schema != SCHEMA_VERSION:
        errors.append(f"schema must be {SCHEMA_VERSION}, got {profile.schema!r}")
    if not profile.odoo_version or not _looks_like_version(profile.odoo_version):
        errors.append(f"odoo_version must look like '18.0', got {profile.odoo_version!r}")
    if profile.edition not in VALID_EDITIONS:
        errors.append(f"edition must be one of {VALID_EDITIONS}, got {profile.edition!r}")
    if profile.hosting not in VALID_HOSTING:
        errors.append(f"hosting must be one of {VALID_HOSTING}, got {profile.hosting!r}")
    if profile.mode not in VALID_MODES:
        errors.append(f"mode must be one of {VALID_MODES}, got {profile.mode!r}")
    if profile.hosting == "online" and profile.odoo_source:
        errors.append("hosting is 'online' but odoo_source is set; Online has no source to read")
    return errors


def _looks_like_version(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 2 and all(p.isdigit() for p in parts)
