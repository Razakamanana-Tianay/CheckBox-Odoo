"""Tests for checkbox.profile against the hand-written stub trees.

Each stub mimics a real Odoo checkout closely enough that detect() exercises
real parsing logic (see tests/fixtures/stubs/*/odoo/release.py headers for
what was checked against upstream and when).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox import profile as profile_mod  # noqa: E402

STUBS = REPO_ROOT / "tests" / "fixtures" / "stubs"


def test_detect_odoo18_ce_version_and_edition():
    prof = profile_mod.detect(STUBS / "odoo18-ce")
    assert prof.odoo_version == "18.0"
    assert prof.edition == "community"
    assert "odoo_version" in prof.detected
    assert "edition" in prof.detected


def test_detect_odoo17_ce_version():
    prof = profile_mod.detect(STUBS / "odoo17-ce")
    assert prof.odoo_version == "17.0"
    assert prof.edition == "community"


def test_detect_odoo18_ee_edition():
    prof = profile_mod.detect(STUBS / "odoo18-ee")
    assert prof.odoo_version == "18.0"
    assert prof.edition == "enterprise"
    assert prof.enterprise_source is not None
    # enterprise_source is the addons *root* (mirrors odoo_source's semantics
    # in Appendix B), not the specific web_enterprise module dir used as the
    # detection signal.
    assert Path(prof.enterprise_source).name == "enterprise"


def test_detect_sibling_checkout_layout(tmp_path):
    # Appendix B's "odoo_source": "../odoo" convention: the project root and
    # a sibling checkout named "odoo" live side by side, and that sibling IS
    # a full checkout (its own odoo/release.py inside it), not release.py
    # sitting directly in the sibling dir. Regression test for the bug the
    # advisor caught: _resolve_release_py's sibling candidate originally had
    # only one "odoo" segment, so odoo_source resolved one level too high.
    project = tmp_path / "myproject"
    project.mkdir()
    sibling_checkout = tmp_path / "odoo"
    (sibling_checkout / "odoo").mkdir(parents=True)
    (sibling_checkout / "odoo" / "release.py").write_text(
        "version_info = (18, 0, 0, 'final', 0, '')\n"
    )

    prof = profile_mod.detect(project)
    assert prof.odoo_version == "18.0"
    assert prof.odoo_source == str(sibling_checkout)


def test_detect_finds_addon_paths():
    prof = profile_mod.detect(STUBS / "odoo18-ce")
    assert "addon_paths" in prof.detected
    assert "addons" in prof.detected["addon_paths"]
    assert (
        "odoo/addons" in prof.detected["addon_paths"]
        or "odoo\\addons" in prof.detected["addon_paths"]
    )


def test_detect_on_empty_dir_does_not_raise(tmp_path):
    prof = profile_mod.detect(tmp_path)
    assert prof.odoo_version is None
    assert prof.edition is None
    assert prof.detected == {}


def test_parse_version_info_resolves_name_reference():
    # The exact quirk the docstring in profile.py explains: version_info's
    # 4th element is the *name* FINAL, not the string 'final'.
    version_info = profile_mod._parse_version_info(STUBS / "odoo18-ce" / "odoo" / "release.py")
    assert version_info == (18, 0, 0, "final", 0, "")


def test_validate_accepts_a_complete_profile():
    prof = profile_mod.Profile(
        odoo_version="18.0",
        edition="community",
        hosting="on-premise",
        mode="full",
    )
    assert profile_mod.validate(prof) == []


def test_validate_rejects_bad_edition():
    prof = profile_mod.Profile(odoo_version="18.0", edition="pro", hosting="on-premise")
    errors = profile_mod.validate(prof)
    assert any("edition" in e for e in errors)


def test_validate_rejects_missing_version():
    prof = profile_mod.Profile(edition="community", hosting="on-premise")
    errors = profile_mod.validate(prof)
    assert any("odoo_version" in e for e in errors)


def test_validate_rejects_online_with_source():
    prof = profile_mod.Profile(
        odoo_version="18.0", edition="community", hosting="online", odoo_source="../odoo"
    )
    errors = profile_mod.validate(prof)
    assert any("online" in e for e in errors)


def test_write_then_load_roundtrip(tmp_path):
    prof = profile_mod.Profile(odoo_version="18.0", edition="community", hosting="on-premise")
    profile_mod.write(tmp_path, prof)
    loaded = profile_mod.load(tmp_path)
    assert loaded.odoo_version == "18.0"
    assert loaded.edition == "community"
    assert (tmp_path / ".checkbox" / "profile.json").is_file()


def test_write_output_is_pretty_json(tmp_path):
    prof = profile_mod.Profile(odoo_version="18.0", edition="community", hosting="on-premise")
    path = profile_mod.write(tmp_path, prof)
    data = json.loads(path.read_text())
    assert data["odoo_version"] == "18.0"
    assert data["schema"] == profile_mod.SCHEMA_VERSION


def test_load_missing_profile_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        profile_mod.load(tmp_path)
