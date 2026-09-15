"""XML/CSV risk scanner. docs/ARCHITECTURE.md §6.2's "XML/CSV files" bullet list.

ir.rule / ir.model.access detection reads the `model` field's XML `<record
model="ir.model.data">`... in practice ir.rule and ir.model.access.csv
records are identified by their own record `model="ir.rule"` attribute (XML)
or by being a `.csv` file named `ir.model.access.csv` (Odoo's own naming
convention for that file, universal across addons).
"""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _finding(rule_id: str, tier: str, path: Path, line: int | None, detail: str) -> dict[str, Any]:
    return {"rule_id": rule_id, "tier": tier, "file": str(path), "line": line, "detail": detail}


def _scan_xml_records(root: ET.Element, rules: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    xml_rules = rules.get("xml_patterns", {})
    for record in root.iter("record"):
        model = record.get("model", "")
        if model == "ir.rule" and "ir.rule" in xml_rules:
            rule = xml_rules["ir.rule"]
            findings.append(
                _finding("xml:ir.rule", rule["tier"], path, None, rule.get("detail", ""))
            )
        elif model == "ir.model.access" and "ir.model.access" in xml_rules:
            rule = xml_rules["ir.model.access"]
            findings.append(
                _finding("xml:ir.model.access", rule["tier"], path, None, rule.get("detail", ""))
            )
        if record.get("noupdate") == "1" and "noupdate_data" in xml_rules:
            rule = xml_rules["noupdate_data"]
            findings.append(
                _finding("xml:noupdate", rule["tier"], path, None, rule.get("detail", ""))
            )
    if root.get("noupdate") == "1" and "noupdate_data" in xml_rules:
        rule = xml_rules["noupdate_data"]
        findings.append(_finding("xml:noupdate", rule["tier"], path, None, rule.get("detail", "")))

    for tag in ("menuitem", "act_window", "button"):
        for el in root.iter(tag):
            if el.get("groups") and "groups_on_menu_or_action" in xml_rules:
                rule = xml_rules["groups_on_menu_or_action"]
                findings.append(
                    _finding(
                        "xml:groups_on_menu_or_action",
                        rule["tier"],
                        path,
                        None,
                        rule.get("detail", ""),
                    )
                )
    return findings


def scan_xml(path: Path, rules: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return []
    return _scan_xml_records(root, rules, path)


def scan_csv(path: Path, rules: dict[str, Any]) -> list[dict[str, Any]]:
    """Odoo's own convention: a CSV named `ir.model.access.csv` defines
    `ir.model.access` records; there's no per-row `model` field to check
    the way XML has, so the filename itself is the signal."""
    path = Path(path)
    if path.name != "ir.model.access.csv":
        return []
    xml_rules = rules.get("xml_patterns", {})
    if "ir.model.access" not in xml_rules:
        return []
    try:
        with path.open(encoding="utf-8") as handle:
            row_count = sum(1 for _ in csv.reader(handle)) - 1  # minus header
    except OSError:
        return []
    if row_count <= 0:
        return []
    rule = xml_rules["ir.model.access"]
    return [
        _finding(
            "csv:ir.model.access",
            rule["tier"],
            path,
            None,
            f"{row_count} access rule row(s): {rule.get('detail', '')}",
        )
    ]


def scan(path: Path, rules: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(path)
    if path.suffix == ".csv":
        return scan_csv(path, rules)
    if path.suffix == ".xml":
        return scan_xml(path, rules)
    return []
