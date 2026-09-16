"""Load risk rules (common.json + per-version overlay) and verify them
against real Odoo source.

docs/ARCHITECTURE.md §6.2: "Every model and method entry is checked by
`checkbox rules verify --version X --odoo-src PATH`. The command fails if
the model or method is not defined in the referenced source file. No entry
is merged without passing this check, which is what keeps model-memory
hallucinations out of the risk data." This module is that check.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

_RULES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "rules" / "risk"


def load_common() -> dict[str, Any]:
    return json.loads((_RULES_DIR / "common.json").read_text(encoding="utf-8"))


def load_version(version: str) -> dict[str, Any]:
    path = _RULES_DIR / f"{version}.json"
    if not path.is_file():
        raise FileNotFoundError(f"no risk rules for version {version!r} (expected {path})")
    return json.loads(path.read_text(encoding="utf-8"))


def available_versions() -> list[str]:
    """Rule-file versions present in the rules dir, sorted ascending."""
    versions = []
    for path in _RULES_DIR.glob("*.json"):
        if path.name == "common.json":
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        versions.append(path.stem)
    return sorted(set(versions))


def load(version: str) -> dict[str, Any]:
    """Merge common.json with the version overlay's `models`.

    Only `models` is per-version; python_calls/xml_patterns/etc. come from
    common.json only -- no version has needed to override one of those yet.

    A version with no overlay file yet (e.g. 19.0 while verify has only
    cleared 17.0/18.0) falls back to the highest *available* overlay and
    labels it in `base_version`. Deterministic, fail-open (hooks must never
    raise on a stale version), and explicit that the rules may predate the
    profile's version -- a card's evidence is what pins exactness, not the
    classifier default.
    """
    try:
        overlay = load_version(version)
    except FileNotFoundError:
        versions = available_versions()
        if not versions:
            raise
        fallback = versions[-1]
        if fallback != version:
            import warnings

            warnings.warn(
                f"no risk rules for version {version!r}; using {fallback!r} (unverified "
                "model-method data for the newer version is never guessed)",
                RuntimeWarning,
                stacklevel=2,
            )
        overlay = load_version(fallback)
        version = fallback
    merged = dict(load_common())
    merged["version"] = version
    merged["models"] = overlay.get("models", {})
    return merged


def _class_model_names(class_node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for stmt in class_node.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name) or target.id not in ("_name", "_inherit"):
            continue
        value = stmt.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            names.append(value.value)
        elif isinstance(value, (ast.List, ast.Tuple)):
            names.extend(
                e.value
                for e in value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            )
    return names


def _method_names_for_model(tree: ast.Module, model_name: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and model_name in _class_model_names(node):
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(stmt.name)
    return names


def verify(version: str, odoo_src: Path) -> list[str]:
    """Check every model/method entry in the version overlay against real
    source under *odoo_src*. Returns a list of error strings; empty means
    every entry checks out."""
    errors: list[str] = []
    overlay = load_version(version)
    odoo_src = Path(odoo_src)

    for model_name, entry in overlay.get("models", {}).items():
        source_rel = entry.get("source")
        if not source_rel:
            errors.append(f"{model_name}: rule entry has no 'source' field")
            continue
        source_path = odoo_src / source_rel
        if not source_path.is_file():
            errors.append(f"{model_name}: source file not found: {source_path}")
            continue
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{model_name}: could not parse {source_path}: {exc}")
            continue

        has_model = any(
            isinstance(node, ast.ClassDef) and model_name in _class_model_names(node)
            for node in ast.walk(tree)
        )
        if not has_model:
            errors.append(
                f"{model_name}: no class with _name/_inherit == {model_name!r} in {source_path}"
            )
            continue

        found_methods = _method_names_for_model(tree, model_name)
        for method_name in entry.get("methods", {}):
            if method_name not in found_methods:
                errors.append(f"{model_name}.{method_name}: not found in {source_path}")

    return errors
