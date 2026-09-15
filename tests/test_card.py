"""Tests for checkbox.card: parse, validate, next_id, lint_pii."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox import card as card_mod  # noqa: E402
from checkbox.profile import Profile  # noqa: E402

SAMPLE_CARD = """\
# 0007 — PO approval above threshold

```checkbox-card
id: 0007
need: Purchase orders above 5,000 require manager approval before confirmation
profile: 18.0 / community / on-premise
verdict: config
evidence: source | addons/purchase/... (settings field) ; docs | purchase approval page
steps: Purchase > Configuration > Settings > enable order approval, set minimum amount
addons: -
extension_point: -
tier: -
upgrade_cost: none
status: proposed
```

Context, rejected options, open questions (free text).
"""


def test_parse_extracts_all_fields():
    card = card_mod.parse(SAMPLE_CARD)
    assert card["id"] == "0007"
    assert card["verdict"] == "config"
    assert card["status"] == "proposed"
    assert card["addons"] == []


def test_parse_splits_evidence_into_kind_ref_pairs():
    card = card_mod.parse(SAMPLE_CARD)
    assert card["evidence"] == [
        {"kind": "source", "ref": "addons/purchase/... (settings field)"},
        {"kind": "docs", "ref": "purchase approval page"},
    ]


def test_parse_raises_without_fence():
    import pytest

    with pytest.raises(ValueError):
        card_mod.parse("# just a heading, no card block")


def test_validate_accepts_the_sample_card():
    card = card_mod.parse(SAMPLE_CARD)
    assert card_mod.validate(card) == []


def test_validate_rejects_bad_verdict():
    card = card_mod.parse(SAMPLE_CARD)
    card["verdict"] = "maybe"
    errors = card_mod.validate(card)
    assert any("verdict" in e for e in errors)


def test_validate_requires_tier_for_code_verdict():
    card = card_mod.parse(SAMPLE_CARD)
    card["verdict"] = "code"
    card["tier"] = "-"
    errors = card_mod.validate(card)
    assert any("tier is required" in e for e in errors)


def test_validate_allows_code_verdict_with_tier_set():
    card = card_mod.parse(SAMPLE_CARD)
    card["verdict"] = "code"
    card["tier"] = "green"
    card["addons"] = []
    errors = card_mod.validate(card)
    assert not any("tier is required" in e for e in errors)


def test_validate_requires_non_unverified_evidence_for_config():
    card = card_mod.parse(SAMPLE_CARD)
    card["evidence"] = [{"kind": "unverified", "ref": "I think so"}]
    errors = card_mod.validate(card)
    assert any("evidence" in e for e in errors)


def test_validate_docs_only_evidence_is_sufficient():
    card = card_mod.parse(SAMPLE_CARD)
    card["evidence"] = [{"kind": "docs", "ref": "some doc page"}]
    assert card_mod.validate(card) == []


def test_validate_rejects_addon_outside_custom_addons():
    card = card_mod.parse(SAMPLE_CARD)
    card["verdict"] = "code"
    card["tier"] = "green"
    card["addons"] = ["not_a_custom_addon"]
    profile = Profile(custom_addons=["my_custom_addon"])
    errors = card_mod.validate(card, profile=profile)
    assert any("custom_addons" in e for e in errors)


def test_validate_accepts_addon_inside_custom_addons():
    card = card_mod.parse(SAMPLE_CARD)
    card["verdict"] = "code"
    card["tier"] = "green"
    card["addons"] = ["my_custom_addon"]
    profile = Profile(custom_addons=["my_custom_addon"])
    assert card_mod.validate(card, profile=profile) == []


def test_lint_pii_flags_email():
    warnings = card_mod.lint_pii("Contact: jane.doe@example.com about this")
    assert warnings
    assert "email" in warnings[0]


def test_lint_pii_flags_iban_like_token():
    warnings = card_mod.lint_pii("Refund to FR1420041010050500013M02606")
    assert warnings


def test_lint_pii_clean_text_has_no_warnings():
    assert card_mod.lint_pii(SAMPLE_CARD) == []


def test_validate_with_raw_text_surfaces_pii_as_errors():
    card = card_mod.parse(SAMPLE_CARD)
    dirty = SAMPLE_CARD + "\nRequested by jane.doe@example.com.\n"
    errors = card_mod.validate(card, raw_text=dirty)
    assert any("PII" in e for e in errors)


def test_next_id_on_empty_dir_is_0001(tmp_path):
    assert card_mod.next_id(tmp_path / "decisions") == "0001"


def test_next_id_increments_past_existing_cards(tmp_path):
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    (decisions / "0001-first.md").write_text("x")
    (decisions / "0007-po-approval.md").write_text("x")
    assert card_mod.next_id(decisions) == "0008"
