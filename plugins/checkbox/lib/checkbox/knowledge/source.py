"""Build the source feature index from addon manifests and settings signals.

docs/ARCHITECTURE.md §7.1's "source" row: manifests (name, summary,
category, depends), res.config.settings fields and their labels, settings
view blocks (titles and help). Model `_description` and menu names from
that same row are deferred -- the flagship example (po_order_approval,
verified against addons/purchase/models/res_config_settings.py and
addons/purchase/views/res_config_settings_views.xml on the 18.0 branch,
2026-09-15) is fully covered by manifests + settings fields + settings
views alone, and P3's exit criterion doesn't need more than that. Add
_description/menu indexing later if a real seed case needs it.

Never imports Odoo or executes project code (repo CLAUDE.md convention):
manifests are read with `ast.literal_eval`, Python settings fields with
`ast`, XML settings views with `xml.etree.ElementTree`.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_SETTINGS_FIELD_TYPES = ("Boolean", "Selection")
_SNIPPET_MAX = 300


def _iter_addon_dirs(addons_root: Path):
    if not addons_root.is_dir():
        return
    for child in sorted(addons_root.iterdir()):
        if (child / "__manifest__.py").is_file():
            yield child


def _read_manifest(manifest_path: Path) -> dict[str, Any] | None:
    try:
        tree = ast.parse(manifest_path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
            try:
                return ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                return None
    return None


def _manifest_doc(addon_dir: Path, manifest: dict[str, Any], version: str) -> dict[str, Any]:
    name = manifest.get("name", addon_dir.name)
    summary = str(manifest.get("summary") or manifest.get("description") or "")
    return {
        "kind": "source",
        "ref": str(addon_dir / "__manifest__.py"),
        "line": None,
        "title": f"{name} ({addon_dir.name})",
        "snippet": summary[:_SNIPPET_MAX],
        "version": version,
    }


def _inherits_res_config_settings(class_node: ast.ClassDef) -> bool:
    for stmt in class_node.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name) or target.id not in ("_inherit", "_name"):
            continue
        value = stmt.value
        names: list[str] = []
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            names = [value.value]
        elif isinstance(value, (ast.List, ast.Tuple)):
            names = [
                e.value
                for e in value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]
        if "res.config.settings" in names:
            return True
    return False


def _first_str_arg(call: ast.Call) -> str:
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return ""


def _kwarg_str(call: ast.Call, name: str) -> str:
    for kw in call.keywords:
        if (
            kw.arg == name
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return kw.value.value
    return ""


def _settings_field_docs(py_file: Path, version: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return []
    docs: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not _inherits_res_config_settings(node):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                continue
            target = stmt.targets[0]
            call = stmt.value
            if not isinstance(target, ast.Name):
                continue
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
                continue
            if call.func.attr not in _SETTINGS_FIELD_TYPES:
                continue
            label = _first_str_arg(call)
            help_text = _kwarg_str(call, "help")
            snippet = " -- ".join(p for p in (label, help_text) if p) or target.id
            docs.append(
                {
                    "kind": "source",
                    "ref": str(py_file),
                    "line": stmt.lineno,
                    "title": f"res.config.settings.{target.id}",
                    "snippet": snippet[:_SNIPPET_MAX],
                    "version": version,
                }
            )
    return docs


def _setting_view_docs(xml_file: Path, version: str) -> list[dict[str, Any]]:
    try:
        tree = ET.parse(xml_file)
    except (ET.ParseError, OSError):
        return []
    docs: list[dict[str, Any]] = []
    for block in tree.getroot().iter("block"):
        block_title = block.get("title", "")
        for setting in block.iter("setting"):
            setting_id = setting.get("id", "")
            title = setting.get("string", "") or setting_id
            help_text = setting.get("help", "")
            snippet = " -- ".join(p for p in (block_title, help_text) if p) or title
            docs.append(
                {
                    "kind": "source",
                    "ref": str(xml_file),
                    "line": None,
                    "title": f"Settings: {title}" if title else "Settings",
                    "snippet": snippet[:_SNIPPET_MAX],
                    "version": version,
                }
            )
    return docs


def build(addons_roots: list[Path], version: str) -> list[dict[str, Any]]:
    """Return a flat list of Evidence-shaped dicts (`kind: "source"`) for
    every installable addon under *addons_roots*."""
    docs: list[dict[str, Any]] = []
    for addons_root in addons_roots:
        for addon_dir in _iter_addon_dirs(Path(addons_root)):
            manifest = _read_manifest(addon_dir / "__manifest__.py")
            if manifest is None:
                continue
            docs.append(_manifest_doc(addon_dir, manifest, version))
            for py_file in addon_dir.rglob("*.py"):
                docs.extend(_settings_field_docs(py_file, version))
            for xml_file in addon_dir.rglob("*.xml"):
                docs.extend(_setting_view_docs(xml_file, version))
    return docs
