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
PORT_OF_LOADING_FIELD = FIXTURES / "diffs" / "port_of_loading_field.py"
PORT_OF_LOADING_VIEW = FIXTURES / "diffs" / "port_of_loading_view.xml"
BILL_REF_OVERRIDE = FIXTURES / "diffs" / "bill_ref_required_override.py"


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
    # 20.0 has no overlay yet (not released when this was written -- verified
    # via `git ls-remote --heads github.com/odoo/odoo.git`, 2026-09-15: only
    # up to 19.0 exists). 19.0 itself got a real, verified overlay in P7, so
    # this test moved to 20.0 to keep covering the fail-open path: load()
    # must fail open onto the newest available overlay and say so, not raise.
    with pytest.warns(RuntimeWarning, match="20.0"):
        merged = rules_mod.load("20.0")
    assert merged["version"] == "19.0"


# -- P5 seed-case ground truth (docs/ARCHITECTURE.md §11.3) ------------------
# These fixtures back the expected tier for two eval seed cases whose
# expected answer is a claim about checkbox's *own* classifier, not about
# Odoo -- so the ground truth is this test, not a source citation.


def test_port_of_loading_field_is_green():
    # A plain stored Char field via _inherit, no risky call -- the
    # `port-of-loading` seed case expects tier: green.
    assert _tier(PORT_OF_LOADING_FIELD) == "green"


def test_port_of_loading_view_is_green():
    # A plain xpath view inheritance, no ir.rule/access/groups/noupdate --
    # the `port-of-loading` seed case expects tier: green.
    assert _tier(PORT_OF_LOADING_VIEW) == "green"


def test_bill_ref_required_override_is_red():
    # Overriding account.move.action_post is extension point #5 (§4.3):
    # "red by definition". The `bill-ref-required` seed case expects
    # tier: red regardless of whether the verdict is nocode or code.
    assert _tier(BILL_REF_OVERRIDE, version="17.0") == "red"
    rules = _reasons(BILL_REF_OVERRIDE, version="17.0")
    assert "model-method:account.move.action_post" in rules


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


# -- existing rules, shapes they used to miss (2026-10-11 review) -------------


def _classify_text(tmp_path: Path, name: str, body: str) -> dict:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return classify_mod.classify_file(path, "18.0")


@pytest.mark.parametrize(
    "receiver",
    ["request.env.cr", "move.env.cr", "self.env.cr", "self._cr", "cr", "records.sudo().env.cr"],
)
def test_raw_sql_is_red_on_any_cursor_receiver(tmp_path, receiver):
    body = f"def f(self, move, cr, request, records):\n    {receiver}.execute('SELECT 1')\n"
    result = _classify_text(tmp_path, "x.py", body)
    assert "python_call:execute" in [r["rule_id"] for r in result["reasons"]]
    assert result["tier"] == "red"


def test_execute_on_a_non_cursor_stays_green(tmp_path):
    body = "def f(pool, job):\n    pool.execute(job)\n    job.runner.execute()\n"
    assert _classify_text(tmp_path, "x.py", body)["tier"] == "green"


def test_superuser_id_attribute_form_is_red(tmp_path):
    body = "import odoo\n\ndef f(env):\n    return env(user=odoo.SUPERUSER_ID)\n"
    result = _classify_text(tmp_path, "x.py", body)
    assert [r["rule_id"] for r in result["reasons"]] == ["python_name:SUPERUSER_ID"]


def test_noupdate_on_a_data_element_is_amber(tmp_path):
    body = "<odoo><data noupdate='1'><record id='a' model='res.partner'/></data></odoo>"
    result = _classify_text(tmp_path, "data.xml", body)
    assert [r["rule_id"] for r in result["reasons"]] == ["xml:noupdate"]
    assert result["tier"] == "amber"


def test_unparseable_xml_is_amber_like_unparseable_python(tmp_path):
    result = _classify_text(tmp_path, "broken.xml", "<odoo><record model='ir.rule'>")
    assert [r["rule_id"] for r in result["reasons"]] == ["parse-error"]
    assert result["tier"] == "amber"


# -- rules §6.1 lists that had no detector, and the wider model set ------------

_M = "from odoo import api, fields, models\n\n\n"


@pytest.mark.parametrize(
    ("name", "body", "tier", "rule_id"),
    [
        (
            "aml.py",
            _M + "class L(models.Model):\n    _inherit = 'account.move.line'\n",
            "red",
            "model:account.move.line",
        ),
        (
            "pay.py",
            _M
            + "class P(models.Model):\n    _inherit = 'account.payment'\n    def action_post(self):\n        return super().action_post()\n",  # noqa: E501 -- one-line source sample
            "red",
            "model-method:account.payment.action_post",
        ),
        (
            "tax.py",
            _M + "class T(models.Model):\n    _inherit = 'account.tax'\n",
            "red",
            "model:account.tax",
        ),
        (
            "quant.py",
            _M + "class Q(models.Model):\n    _inherit = 'stock.quant'\n",
            "red",
            "model:stock.quant",
        ),
        (
            "seq.py",
            _M
            + "class S(models.Model):\n    _inherit = 'ir.sequence'\n    def _next(self, sequence_date=None):\n        return '1'\n",  # noqa: E501 -- one-line source sample
            "red",
            "model-method:ir.sequence._next",
        ),
        (
            "stored.py",
            _M
            + "class S(models.Model):\n    _inherit = 'sale.order'\n    x = fields.Float(compute='_c', store=True)\n",  # noqa: E501 -- one-line source sample
            "amber",
            "python:stored_compute",
        ),
        (
            "su.py",
            "def f(self):\n    return self.env(su=True)['res.partner'].search([])\n",
            "red",
            "python:su_true",
        ),
        (
            "patch.py",
            "from odoo.addons.account.models.account_move import AccountMove\n\n\ndef _post(self, soft=True):\n    return self\n\n\nAccountMove._post = _post\n",  # noqa: E501 -- one-line source sample
            "red",
            "python:monkeypatch",
        ),
        (
            "orm.py",
            "def f(self):\n    self.env['account.move.line'].search([]).write({'account_id': 1})\n",
            "red",
            "orm_write:account.move.line",
        ),
        (
            "orm2.py",
            "def f(self):\n    self.env['account.move'].sudo().create({})\n",
            "red",
            "orm_write:account.move",
        ),
        (
            "cron.xml",
            "<odoo><record id='c' model='ir.cron'><field name='code'>model.run()</field></record></odoo>",  # noqa: E501 -- one-line source sample
            "amber",
            "xml:ir.cron",
        ),
        (
            "action.xml",
            "<odoo><record id='a' model='ir.actions.server'><field name='code'>x = 1</field></record></odoo>",  # noqa: E501 -- one-line source sample
            "amber",
            "xml:server_code",
        ),
        (
            "auto.xml",
            "<odoo><record id='a' model='base.automation'/></odoo>",
            "amber",
            "xml:server_code",
        ),
        (
            "delete.xml",
            "<odoo><delete model='res.partner' id='base.x'/></odoo>",
            "amber",
            "xml:data_operation",
        ),
        (
            "delete_rule.xml",
            "<odoo><delete model='ir.rule' id='account.account_move_comp_rule'/></odoo>",
            "red",
            "xml:data_operation",
        ),
        (
            "function.xml",
            "<odoo><function model='account.move' name='action_post'/></odoo>",
            "red",
            "xml:data_operation",
        ),
    ],
)
def test_rule_detects(tmp_path, name, body, tier, rule_id):
    result = _classify_text(tmp_path, name, body)
    assert rule_id in [r["rule_id"] for r in result["reasons"]]
    assert result["tier"] == tier


@pytest.mark.parametrize(
    ("name", "body"),
    [
        (
            "plain_compute.py",
            _M
            + "class S(models.Model):\n    _inherit = 'sale.order'\n    x = fields.Float(compute='_c')\n    y = fields.Char(store=True)\n",  # noqa: E501 -- one-line source sample
        ),
        ("su_false.py", "def f(self):\n    return self.env(su=False)\n"),
        (
            "own_attr.py",
            "class A:\n    def set(self):\n        self._post = 1\n        self.helper.name = 2\n",
        ),
        (
            "orm_other.py",
            "def f(self):\n    self.env['res.partner'].create({})\n    self.env['account.move'].search([])\n",  # noqa: E501 -- one-line source sample
        ),
        (
            "view.xml",
            "<odoo><record id='v' model='ir.ui.view'><field name='arch' type='xml'><form/></field></record></odoo>",  # noqa: E501 -- one-line source sample
        ),
    ],
)
def test_rule_stays_quiet(tmp_path, name, body):
    assert _classify_text(tmp_path, name, body) == {"tier": "green", "reasons": []}


def test_groups_field_on_a_menu_record_is_amber(tmp_path):
    body = (
        "<odoo><record id='m' model='ir.ui.menu'>"
        "<field name='groups_id' eval='[(4, ref(\"base.group_user\"))]'/></record></odoo>"
    )
    result = _classify_text(tmp_path, "menu.xml", body)
    assert [r["rule_id"] for r in result["reasons"]] == ["xml:groups_on_menu_or_action"]


@pytest.mark.parametrize("version", ["17.0", "18.0", "19.0"])
def test_every_overlay_entry_names_a_source(version):
    overlay = rules_mod.load_version(version)
    assert len(overlay["models"]) >= 11
    assert all(entry.get("source") for entry in overlay["models"].values())
