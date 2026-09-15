"""Tests for the four P4 guard hooks: pre_edit, pre_bash, post_edit, stop.

Unit-level (call each hook's `_run()` with an in-memory payload, capture
stdout) plus one end-to-end drive of `bin/checkbox hook <event>` on the
committed fixtures for the pre-edit deny and the stop block.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox import session as session_mod  # noqa: E402
from checkbox.hooks import post_edit, pre_bash, pre_edit, stop  # noqa: E402

PROJECT_18CE = REPO_ROOT / "tests" / "fixtures" / "projects" / "18-ce"
PROJECT_STRICT = REPO_ROOT / "tests" / "fixtures" / "projects" / "18-ce-strict"
BIN = REPO_ROOT / "plugins" / "checkbox" / "bin" / "checkbox"
HOOK_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "hooks"
SESSION_ID = "test-session-1"

_PAYLOAD = {
    "session_id": SESSION_ID,
    "transcript_path": "/tmp/test-transcript.jsonl",
    "cwd": str(PROJECT_18CE),
    "hook_event_name": "PreToolUse",
    "tool_name": "Write",
    "tool_input": {"file_path": "addons/po_approve/models/account_move.py"},
}


def _maybe_strict(monkeypatch):
    monkeypatch.delenv("CHECKBOX_MODE", raising=False)


def test_pre_edit_denies_strict_without_card(capsys, monkeypatch):
    # PROJECT_STRICT's profile.json already has mode: strict -- no need to
    # mutate a committed fixture at test time (that risked leaving a stray
    # local.json in PROJECT_18CE behind on a failure, silently flipping
    # every other test in this module from full to strict).
    _maybe_strict(monkeypatch)
    payload = dict(_PAYLOAD)
    payload["cwd"] = str(PROJECT_STRICT)
    pre_edit._run(payload)
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    reason = result["hookSpecificOutput"]["permissionDecisionReason"]
    assert "'po_approve'" in reason
    assert "approve" in reason


def test_pre_edit_reminds_in_full_mode(capsys):
    pre_edit._run(dict(_PAYLOAD))
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "additionalContext" in payload["hookSpecificOutput"]
    assert "permissionDecision" not in payload["hookSpecificOutput"]


def test_pre_edit_ignores_edits_outside_custom_addons(capsys, monkeypatch):
    _maybe_strict(monkeypatch)
    monkeypatch.setenv("CHECKBOX_MODE", "strict")
    payload = dict(_PAYLOAD)
    payload["tool_input"] = {"file_path": "odoo/addons/base/models/res_partner.py"}
    pre_edit._run(payload)
    assert capsys.readouterr().out == ""


def test_pre_edit_silent_when_mode_lite(capsys, monkeypatch):
    monkeypatch.setenv("CHECKBOX_MODE", "lite")
    pre_edit._run(dict(_PAYLOAD))
    assert capsys.readouterr().out == ""


def test_pre_bash_denies_approve(capsys):
    pre_bash._run(
        {
            "cwd": str(PROJECT_18CE),
            "tool_name": "Bash",
            "tool_input": {"command": "checkbox approve 0001"},
        }
    )
    out = capsys.readouterr().out
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pre_bash_denies_approvals_write(capsys):
    pre_bash._run(
        {
            "cwd": str(PROJECT_18CE),
            "tool_name": "Bash",
            "tool_input": {"command": "echo '{}' > .checkbox/approvals.json"},
        }
    )
    out = capsys.readouterr().out
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pre_bash_allows_reading_approvals(capsys):
    pre_bash._run(
        {
            "cwd": str(PROJECT_18CE),
            "tool_name": "Bash",
            "tool_input": {"command": "cat .checkbox/approvals.json"},
        }
    )
    assert capsys.readouterr().out == ""


def test_pre_bash_denies_ledger_sql(capsys):
    pre_bash._run(
        {
            "cwd": str(PROJECT_18CE),
            "tool_name": "Bash",
            "tool_input": {"command": "psql -c 'UPDATE account_move SET x=1'"},
        }
    )
    out = capsys.readouterr().out
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pre_bash_denies_ledger_sql_on_move_lines(capsys):
    # P5 `sql-fix-posted-lines` seed case ground truth: account_move_line
    # (not just account_move) is on the ledger table list.
    pre_bash._run(
        {
            "cwd": str(PROJECT_18CE),
            "tool_name": "Bash",
            "tool_input": {
                "command": 'psql -c "UPDATE account_move_line SET account_id=42 WHERE move_id=7"'
            },
        }
    )
    out = capsys.readouterr().out
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_post_edit_emits_red_context_and_records_addon(capsys):
    session_file = PROJECT_18CE / ".checkbox" / ".session" / f"{SESSION_ID}.json"
    session_file.unlink(missing_ok=True)
    try:
        post_edit._run(dict(_PAYLOAD))
        out = capsys.readouterr().out
        payload = json.loads(out)
        context = payload["hookSpecificOutput"]["additionalContext"]
        assert "RED" in context
        state = session_mod.load(PROJECT_18CE, SESSION_ID)
        assert "po_approve" in state["touched_addons"]
    finally:
        session_file.unlink(missing_ok=True)


def test_post_edit_silent_for_green_file(capsys, tmp_path):
    green = tmp_path / "views.xml"
    green.write_text("<odoo/>", encoding="utf-8")
    post_edit._run(
        {
            "cwd": str(PROJECT_18CE),
            "tool_name": "Write",
            "tool_input": {"file_path": str(green)},
        }
    )
    assert capsys.readouterr().out == ""


def test_stop_blocks_once_then_allows(capsys, tmp_path):
    session_mod.record_touched_addon(PROJECT_18CE, SESSION_ID, "po_approve")
    try:
        r1 = stop._run({"cwd": str(PROJECT_18CE), "session_id": SESSION_ID})
        assert r1 == 2
        captured = capsys.readouterr()
        # Stop's blocking reason must go to stderr, not stdout: per the docs,
        # exit-2 blocking without a JSON decision uses stderr text as the
        # message Claude sees; stdout would just go to the debug log.
        assert captured.out == ""
        assert "stopping blocked once" in captured.err
        assert "`checkbox approve <id>`" in captured.err
        r2 = stop._run({"cwd": str(PROJECT_18CE), "session_id": SESSION_ID})
        assert r2 == 0  # second call: already blocked once, don't loop
    finally:
        (PROJECT_18CE / ".checkbox" / ".session" / f"{SESSION_ID}.json").unlink(missing_ok=True)


def test_stop_allows_when_no_addons_touched(tmp_path):
    result = stop._run({"cwd": str(tmp_path), "session_id": "fresh"})
    assert result == 0


def test_cli_end_to_end_pre_edit_deny():
    result = subprocess.run(
        [str(BIN), "hook", "pre-edit"],
        cwd=REPO_ROOT,
        input=(HOOK_FIXTURES / "pre_edit_strict_no_card.json").read_bytes(),
        capture_output=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
