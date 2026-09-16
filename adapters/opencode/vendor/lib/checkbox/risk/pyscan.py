"""AST-based Python risk scanner. docs/ARCHITECTURE.md §6.2's "Python files" bullet list."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


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


def _call_base_and_attr(node: ast.Call) -> tuple[str, str] | None:
    """For a `base.attr(...)` call, return (base, attr); `base` is the
    dotted chain below the final attribute (e.g. `self.env.cr.execute(...)`
    -> `("env.cr", "execute")`). None if the call isn't attribute-shaped
    (a bare `foo(...)`)."""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    parts: list[str] = []
    cur = func.value
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name) and cur.id != "self":
        parts.append(cur.id)
    return (".".join(reversed(parts)), func.attr) if parts or isinstance(cur, ast.Name) else None


def _finding(rule_id: str, tier: str, path: Path, line: int, detail: str) -> dict[str, Any]:
    return {"rule_id": rule_id, "tier": tier, "file": str(path), "line": line, "detail": detail}


def _scan_class(node: ast.ClassDef, models: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    matched = [m for m in _class_model_names(node) if m in models]
    for model_name in matched:
        entry = models[model_name]
        tier = entry.get("tier", "green")
        findings.append(
            _finding(
                f"model:{model_name}",
                tier,
                path,
                node.lineno,
                f"class touches model {model_name!r} (tier {tier})",
            )
        )
        method_tiers = entry.get("methods", {})
        for stmt in node.body:
            if (
                isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                and stmt.name in method_tiers
            ):
                method_tier = method_tiers[stmt.name]
                findings.append(
                    _finding(
                        f"model-method:{model_name}.{stmt.name}",
                        method_tier,
                        path,
                        stmt.lineno,
                        f"overrides {model_name}.{stmt.name} (tier {method_tier})",
                    )
                )
    return findings


def _scan_call(node: ast.Call, rules: dict[str, Any], path: Path) -> dict[str, Any] | None:
    call = _call_base_and_attr(node)
    if call is None:
        return None
    base, attr = call
    rule = rules.get("python_calls", {}).get(attr)
    if rule is None:
        return None
    restrict = rule.get("on_attribute_of")
    if restrict is not None and base not in restrict:
        return None
    return _finding(
        f"python_call:{attr}", rule["tier"], path, node.lineno, rule.get("detail", attr)
    )


def _scan_controller_decorators(
    node: ast.FunctionDef | ast.AsyncFunctionDef, rules: dict[str, Any], path: Path
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    auth_rules = rules.get("controller_auth", {})
    csrf_rule = rules.get("controller_csrf_exempt", {})
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        for kw in dec.keywords:
            if (
                kw.arg == "auth"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value in auth_rules
            ):
                rule = auth_rules[kw.value.value]
                findings.append(
                    _finding(
                        f"controller_auth:{kw.value.value}",
                        rule["tier"],
                        path,
                        node.lineno,
                        rule.get("detail", ""),
                    )
                )
            if kw.arg == "csrf" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                findings.append(
                    _finding(
                        "controller_csrf_exempt",
                        csrf_rule.get("tier", "red"),
                        path,
                        node.lineno,
                        csrf_rule.get("detail", ""),
                    )
                )
    return findings


def scan(path: Path, rules: dict[str, Any]) -> list[dict[str, Any]]:
    """Scan one Python file against *rules* (checkbox.risk.rules.load()'s output)."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (SyntaxError, OSError, UnicodeDecodeError) as exc:
        return [_finding("parse-error", "amber", path, getattr(exc, "lineno", 0) or 0, str(exc))]

    findings: list[dict[str, Any]] = []
    models = rules.get("models", {})
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            findings.extend(_scan_class(node, models, path))
        elif isinstance(node, ast.Call):
            found = _scan_call(node, rules, path)
            if found:
                findings.append(found)
        elif isinstance(node, ast.Name) and node.id in rules.get("python_names", {}):
            rule = rules["python_names"][node.id]
            findings.append(
                _finding(
                    f"python_name:{node.id}",
                    rule["tier"],
                    path,
                    node.lineno,
                    rule.get("detail", ""),
                )
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            findings.extend(_scan_controller_decorators(node, rules, path))
    return findings
