"""Classifier tests: red recall 100% on fixtures, green/amber stay out, and
`checkbox rules verify` passes against real Odoo source when available
(marked `odoo_src`, skipped otherwise -- see repo CLAUDE.md's $ODOO_SRC
convention).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox.risk import classify as classify_mod  # noqa: E402
from checkbox.risk import rules as rules_mod  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures"
RED_OVERRIDE = FIXTURES / "diffs" / "move_post_override.py"


def _tier(path: Path, version="18.0") -> str:
    return classify_mod.classify_file(path, version)["tier"]


def _reasons(path: Path, version="18.0") -> list[str]:
    return [f["rule_id"] for f in classify_mod.classify_file(path, version)["reasons"]]


# -- red recall --------------------------------------------------------------


def test_move_post_override_is_red():
    assert _tier(RED_OVERRIDE) == "red"
    rules = _reasons(RED_OVERRIDE)
    assert "model:account.move" in rules
    assert "model-method:account.move._post" in rules
    assert "model-method:account.move.action_post" in rules
    assert "python_call:sudo" in rules
    assert "python_call:execute" in rules


def test_ir_rule_xml_is_red(tmp_path):
    xml_file = tmp_path / "ir_rule.xml"
    xml_file.write_text(
        '<odoo><record id="rule_x" model="ir.rule"><field name="name">x</field></record></odoo>',
        encoding="utf-8",
    )
    assert _tier(xml_file) == "red"
    assert "xml:ir.rule" in _reasons(xml_file)


def test_ir_model_access_csv_is_amber(tmp_path):
    csv_file = tmp_path / "ir.model.access.csv"
    csv_file.write_text("id,name,model_id:id,group_id:id,perm_read\nx,x,x,x,1\n", encoding="utf-8")
    assert _tier(csv_file) == "amber"
    assert "csv:ir.model.access" in _reasons(csv_file)


def test_green_settings_view_is_green(tmp_path):
    xml_file = tmp_path / "settings_views.xml"
    xml_file.write_text(
        '<odoo><record id="v" model="ir.ui.view"><field name="name">x</field></record></odoo>',
        encoding="utf-8",
    )
    assert _tier(xml_file) == "green"


def test_with_user_and_superuser_are_red(tmp_path):
    py = tmp_path / "abuse.py"
    py.write_text(
        "from odoo import models\n"
        "class X(models.Model):\n"
        "    _name = 'x.test'\n"
        "    def go(self):\n"
        "        self.with_user(1).write({})\n"
        "        print(SUPERUSER_ID)\n",
        encoding="utf-8",
    )
    assert _tier(py) == "red"
    rules = _reasons(py)
    assert "python_call:with_user" in rules
    assert "python_name:SUPERUSER_ID" in rules


def test_unparseable_python_is_amber(tmp_path):
    py = tmp_path / "broken.py"
    py.write_text("def x(:\n", encoding="utf-8")
    result = classify_mod.classify_file(py, "18.0")
    assert result["tier"] == "amber"
    assert "parse-error" in [f["rule_id"] for f in result["reasons"]]


def test_non_risk_file_is_green(tmp_path):
    txt = tmp_path / "notes.txt"
    txt.write_text("nothing to see", encoding="utf-8")
    assert _tier(txt) == "green"


def test_version_without_rules_falls_back_to_latest_available():
    # 19.0 has no overlay yet (never verified); load() must fail open onto
    # the newest available overlay and say so, not raise.
    with pytest.warns(RuntimeWarning, match="19.0"):
        merged = rules_mod.load("19.0")
    assert merged["version"] == "18.0"


# -- real-source verification (skipped when the source checkout is absent) ----


@pytest.mark.odoo_src
def test_rules_verify_real_17_and_18(monkeypatch):
    import os

    sources = {}
    for var in ("ODOO17_SRC", "ODOO18_SRC"):
        value = os.environ.get(var)
        if value:
            sources[var] = Path(value)
    missing = [var for var, path in sources.items() if not path.is_dir()]
    if missing:
        pytest.skip(f"missing source checkouts: {missing}")

    for var, root in sources.items():
        version = "17.0" if var == "ODOO17_SRC" else "18.0"
        errors = rules_mod.verify(version, root)
        assert errors == [], f"{version}: {errors}"


@pytest.mark.odoo_src
def test_rules_verify_real_18_smoke():
    import os

    root = os.environ.get("ODOO18_SRC")
    if not root or not Path(root).is_dir():
        pytest.skip("ODOO18_SRC unset")
    errors = rules_mod.verify("18.0", Path(root))
    assert errors == []
