"""End-to-end CLI smoke tests, driving the real bin/checkbox entry point."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN = REPO_ROOT / "plugins" / "checkbox" / "bin" / "checkbox"
PROJECT_18CE = REPO_ROOT / "tests" / "fixtures" / "projects" / "18-ce"
STUB_18CE = REPO_ROOT / "tests" / "fixtures" / "stubs" / "odoo18-ce"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    # Always go through an explicit interpreter, never rely on the OS
    # resolving bin/checkbox's shebang -- subprocess.run() bypasses shell
    # shebang handling entirely on Windows (WinError 193 for an
    # extension-less script), the same problem D12 solved for hooks.json
    # by always `exec`ing a resolved python rather than the bare script.
    return subprocess.run(
        [sys.executable, str(BIN), *args],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=REPO_ROOT,
        env=env,
    )


def test_doctor_json():
    result = _run("doctor", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["python_version_ok"] is True
    assert "python3_is_windows_store_stub" in data
    assert "bin_checkbox_executable" in data
    assert "mcp_venv" in data


def test_doctor_flags_a_windows_store_python3_stub(tmp_path):
    stub_dir = tmp_path / "WindowsApps"
    stub_dir.mkdir()
    stub = stub_dir / "python3"
    stub.write_text("#!/bin/sh\necho stub\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    env = dict(os.environ) | {"PATH": f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
    result = _run("doctor", "--json", env=env)
    data = json.loads(result.stdout)
    assert data["python3_is_windows_store_stub"] is True


def test_doctor_reports_missing_mcp_venv(tmp_path):
    env = dict(os.environ) | {"CHECKBOX_DATA_DIR": str(tmp_path / "no-venv-here")}
    result = _run("doctor", "--json", env=env)
    data = json.loads(result.stdout)
    assert "not installed" in data["mcp_venv"]


_CARD_TEMPLATE = """\
```checkbox-card
id: {id}
verdict: {verdict}
evidence: source|res.config.settings
addons: -
tier: {tier}
status: {status}
```
"""


def _write_card(
    decisions_dir: Path, card_id: str, status: str, verdict: str = "config", tier: str = "-"
) -> None:
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (decisions_dir / f"{card_id}-x.md").write_text(
        _CARD_TEMPLATE.format(id=card_id, verdict=verdict, tier=tier, status=status)
    )


def test_card_list_json_reports_every_card(tmp_path):
    decisions = tmp_path / ".checkbox" / "decisions"
    _write_card(decisions, "0001", status="approved")
    _write_card(decisions, "0002", status="proposed", verdict="module", tier="amber")

    result = _run("card", "list", "--root", str(tmp_path), "--json")
    assert result.returncode == 0
    cards = json.loads(result.stdout)
    assert [c["id"] for c in cards] == ["0001", "0002"]
    assert [c["status"] for c in cards] == ["approved", "proposed"]


def test_card_list_filters_by_status(tmp_path):
    decisions = tmp_path / ".checkbox" / "decisions"
    _write_card(decisions, "0001", status="approved")
    _write_card(decisions, "0002", status="proposed")

    result = _run("card", "list", "--root", str(tmp_path), "--status", "proposed", "--json")
    cards = json.loads(result.stdout)
    assert [c["id"] for c in cards] == ["0002"]


def test_card_list_with_no_decisions_dir_is_empty_not_an_error(tmp_path):
    result = _run("card", "list", "--root", str(tmp_path), "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout) == []


def test_profile_detect_hints_at_a_nested_checkbox_dir(tmp_path):
    nested = tmp_path / "odoo" / ".checkbox"
    nested.mkdir(parents=True)
    (nested / "profile.json").write_text(
        '{"schema": 1, "odoo_version": "18.0", "edition": "community", "hosting": "on-premise"}'
    )

    result = _run("profile", "detect", str(tmp_path), "--json")
    assert result.returncode == 0
    assert "odoo already has a checkbox profile" in result.stderr
    assert f"checkbox profile detect {tmp_path / 'odoo'}" in result.stderr


def test_profile_detect_silent_when_nothing_nested(tmp_path):
    result = _run("profile", "detect", str(tmp_path), "--json")
    assert result.returncode == 0
    assert result.stderr == ""


def test_ladder_render_with_known_profile():
    result = _run("ladder", "render", "--level", "full", "--root", str(PROJECT_18CE))
    assert result.returncode == 0
    assert "Odoo change policy (checkbox)" in result.stdout


def test_ladder_render_without_profile_fails_cleanly():
    result = _run("ladder", "render", "--root", str(STUB_18CE))
    assert result.returncode == 1
    assert "/checkbox:init" in result.stderr


def test_usage_error_exits_2():
    result = _run("not-a-real-command")
    assert result.returncode == 2


def test_card_next_id_on_project_with_no_decisions_yet():
    result = _run("card", "next-id", "--root", str(PROJECT_18CE), "--json")
    assert result.returncode == 0
    assert '"next_id": "0001"' in result.stdout


def test_card_validate_accepts_a_well_formed_card(tmp_path):
    card_file = tmp_path / "0001-test.md"
    card_file.write_text(
        "# 0001 - test\n\n"
        "```checkbox-card\n"
        "id: 0001\n"
        "need: test need\n"
        "profile: 18.0 / community / on-premise\n"
        "verdict: config\n"
        "evidence: docs | some page\n"
        "steps: do the thing\n"
        "addons: -\n"
        "extension_point: -\n"
        "tier: -\n"
        "upgrade_cost: none\n"
        "status: proposed\n"
        "```\n"
    )
    result = _run("card", "validate", str(card_file), "--root", str(PROJECT_18CE), "--json")
    assert result.returncode == 0
    assert '"valid": true' in result.stdout


def test_card_validate_rejects_a_broken_card(tmp_path):
    card_file = tmp_path / "0002-bad.md"
    card_file.write_text("# 0002 - bad\n\nno fenced block here at all.\n")
    result = _run("card", "validate", str(card_file), "--root", str(PROJECT_18CE))
    assert result.returncode == 1
    assert "error" in result.stderr


def test_mode_show_defaults_to_full():
    result = _run("mode", "show", "--root", str(PROJECT_18CE), "--json")
    assert result.returncode == 0
    assert '"mode": "full"' in result.stdout


def test_mode_set_then_show_roundtrip(tmp_path):
    set_result = _run("mode", "set", "strict", "--root", str(tmp_path), "--json")
    assert set_result.returncode == 0
    show_result = _run("mode", "show", "--root", str(tmp_path), "--json")
    assert '"mode": "strict"' in show_result.stdout


def test_mode_set_rejects_bad_level():
    result = _run("mode", "set", "bogus", "--root", str(PROJECT_18CE))
    assert result.returncode == 2  # argparse choices rejects it before cmd_mode_set runs
