"""Tests for `checkbox setup <host>` (docs/ARCHITECTURE.md §9, phase P9)."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox import setup as setup_mod  # noqa: E402

ADAPTERS = REPO_ROOT / "adapters"


def _install(tmp_path: Path, host: str, **kwargs) -> dict:
    return setup_mod.install(host, tmp_path, adapters=ADAPTERS, **kwargs)


def test_unknown_host_raises(tmp_path):
    with pytest.raises(ValueError):
        setup_mod.install("codex", tmp_path, adapters=ADAPTERS)


def test_cursor_writes_rule_file(tmp_path):
    report = _install(tmp_path, "cursor")
    entry = report["files"][0]
    assert entry["action"] == "write"
    assert entry["written"] is True
    assert entry["existed"] is False
    target = tmp_path / ".cursor" / "rules" / "checkbox.mdc"
    assert target.read_text(encoding="utf-8") == (ADAPTERS / "cursor" / "checkbox.mdc").read_text(
        encoding="utf-8"
    )


def test_cursor_reinstall_overwrites_idempotently(tmp_path):
    _install(tmp_path, "cursor")
    report = _install(tmp_path, "cursor")
    entry = report["files"][0]
    assert entry["action"] == "overwrite"
    assert entry["written"] is True
    assert (tmp_path / ".cursor" / "rules" / "checkbox.mdc").read_text(encoding="utf-8") == (
        ADAPTERS / "cursor" / "checkbox.mdc"
    ).read_text(encoding="utf-8")


def test_windsurf_and_copilot_locations(tmp_path):
    _install(tmp_path, "windsurf")
    assert (tmp_path / ".windsurf" / "rules" / "checkbox.md").is_file()
    _install(tmp_path, "copilot")
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()


def test_dry_run_writes_nothing(tmp_path):
    report = _install(tmp_path, "copilot", dry_run=True)
    assert report["files"][0]["written"] is False
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()


def test_opencode_writes_fresh_agents_md(tmp_path):
    report = _install(tmp_path, "opencode")
    assert report["files"][0]["action"] == "write"
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == (
        ADAPTERS / "AGENTS.md"
    ).read_text(encoding="utf-8")


def test_opencode_merges_into_existing_agents_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("my existing project rules\n", encoding="utf-8")
    report = _install(tmp_path, "opencode")
    assert report["files"][0]["action"] == "append"
    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith("my existing project rules")
    assert "Odoo change policy (checkbox)" in text


def test_opencode_skips_when_already_merged(tmp_path):
    (tmp_path / "AGENTS.md").write_text(
        (ADAPTERS / "AGENTS.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    report = _install(tmp_path, "opencode")
    assert report["files"][0]["action"] == "skip"
    assert report["files"][0]["written"] is False


def test_missing_adapters_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        setup_mod.install("cursor", tmp_path, adapters=tmp_path / "nope")


def test_report_carries_content_sha256(tmp_path):
    report = _install(tmp_path, "cursor")
    entry = report["files"][0]
    expected = hashlib.sha256(
        (ADAPTERS / "cursor" / "checkbox.mdc").read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()
    assert entry["sha256"] == expected
