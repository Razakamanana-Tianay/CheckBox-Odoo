"""Tests for checkbox.approvals: the human approval gate (§5.2)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox import approvals  # noqa: E402


def _card(
    verdict="config",
    tier="-",
    status="proposed",
    evidence="source | addons/purchase/models/res_config_settings.py",
):
    return (
        "# 0001 - test\n\n"
        "```checkbox-card\n"
        "id: 0001\n"
        "need: test need\n"
        "profile: 18.0 / community / on-premise\n"
        f"verdict: {verdict}\n"
        f"evidence: {evidence}\n"
        "steps: do the thing\n"
        "addons: -\n"
        "extension_point: -\n"
        f"tier: {tier}\n"
        "upgrade_cost: none\n"
        f"status: {status}\n"
        "```\n"
    )


def _write_card(tmp_path: Path, text: str, name="0001-test.md") -> Path:
    decisions = tmp_path / ".checkbox" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    path = decisions / name
    path.write_text(text, encoding="utf-8")
    return path


def test_approve_valid_proposed_card(tmp_path):
    path = _write_card(tmp_path, _card())
    record = approvals.approve(tmp_path, "0001", approver="tester", now="2026-09-15T00:00:00+00:00")
    assert record["card_id"] == "0001"
    assert record["approver"] == "tester"
    assert record["hash"] == approvals.card_hash(path.read_text(encoding="utf-8"))
    saved = approvals.read(tmp_path)
    assert saved["0001"]["hash"] == record["hash"]


def test_approve_missing_card_rejected(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="no card '0001'"):
        approvals.approve(tmp_path, "0001")


def test_approve_rejects_invalid_card(tmp_path):
    import pytest

    _write_card(tmp_path, "# 0001 - bad\n\nno fenced block here.\n")
    with pytest.raises(ValueError, match=r"fenced block found"):
        approvals.approve(tmp_path, "0001")


def test_approve_rejects_non_proposed_status(tmp_path):
    import pytest

    _write_card(tmp_path, _card(status="superseded"))
    with pytest.raises(ValueError, match="not 'proposed'"):
        approvals.approve(tmp_path, "0001")


def test_approve_red_card_without_ledger_report_rejected(tmp_path):
    import pytest

    _write_card(tmp_path, _card(verdict="code", tier="red"))
    with pytest.raises(ValueError, match="ledger-reviewer"):
        approvals.approve(tmp_path, "0001")


def test_approve_red_card_with_unverified_evidence_rejected(tmp_path):
    import pytest

    _write_card(tmp_path, _card(verdict="code", tier="red", evidence="unverified | nothing"))
    with pytest.raises(ValueError, match="unverified"):
        approvals.approve(tmp_path, "0001")


def test_approve_red_card_with_ledger_report_accepted(tmp_path):
    path = _write_card(tmp_path, _card(verdict="code", tier="red"))
    path.with_name(f"0001{approvals._LEDGER_SUFFIX}").write_text(
        "ledger-reviewer checklist\nALL OK\n", encoding="utf-8"
    )
    record = approvals.approve(tmp_path, "0001", approver="tester")
    assert record["ledger_report"] == "0001-ledger.md"


def test_editing_an_approved_card_voids_approval(tmp_path):
    _write_card(tmp_path, _card())
    approvals.approve(tmp_path, "0001", approver="tester")
    assert approvals.is_approved(tmp_path, "0001", _card())

    edited = _card().replace("test need", "edited need")
    _write_card(tmp_path, edited)
    assert not approvals.is_approved(tmp_path, "0001", edited)


def test_covers_addon_only_counts_approved_matching_cards(tmp_path):
    _write_card(tmp_path, _card(verdict="code", tier="amber"))
    path = tmp_path / ".checkbox" / "decisions" / "0001-test.md"
    # rewrite the card to name an addon
    path.write_text(_card().replace("addons: -", "addons: po_approve"), encoding="utf-8")

    # not approved yet -> no coverage
    assert approvals.covers_addon(tmp_path, "po_approve") == []

    approvals.approve(tmp_path, "0001", approver="tester")
    assert approvals.covers_addon(tmp_path, "po_approve") == ["0001"]
    assert approvals.covers_addon(tmp_path, "other_addon") == []


def test_covers_addon_drops_card_edited_after_approval(tmp_path):
    path = tmp_path / ".checkbox" / "decisions" / "0001-test.md"
    _write_card(tmp_path, _card().replace("addons: -", "addons: po_approve"))
    approvals.approve(tmp_path, "0001", approver="tester")
    assert approvals.covers_addon(tmp_path, "po_approve") == ["0001"]

    path.write_text(
        _card().replace("addons: -", "addons: po_approve").replace("test need", "tampered"),
        encoding="utf-8",
    )
    assert approvals.covers_addon(tmp_path, "po_approve") == []
