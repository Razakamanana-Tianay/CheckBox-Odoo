"""Tests for the three P2 injection hooks: session_start, prompt, subagent_start.

Unit-level: call each hook's `_run()` directly against an in-memory payload
and capture stdout, so these don't depend on subprocess/stdin plumbing.
One end-to-end test per hook drives the real `bin/checkbox hook <event>`
entry point against the committed fixtures in tests/fixtures/hooks/, the
same way the dry-run commands in the repo's CLAUDE.md do.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox.hooks import prompt, session_start, subagent_start  # noqa: E402

PROJECT_18CE = REPO_ROOT / "tests" / "fixtures" / "projects" / "18-ce"
STUB_18CE = REPO_ROOT / "tests" / "fixtures" / "stubs" / "odoo18-ce"
BIN = REPO_ROOT / "plugins" / "checkbox" / "bin" / "checkbox"


# -- session_start -----------------------------------------------------------


def test_session_start_emits_full_ladder_for_known_profile(capsys):
    session_start._run({"cwd": str(PROJECT_18CE)})
    out = capsys.readouterr().out
    assert "Odoo change policy (checkbox)" in out
    assert "18.0" in out
    assert out.startswith("#")  # raw stdout, no JSON wrapper (plain-stdout event)


def test_session_start_notes_missing_profile(capsys):
    session_start._run({"cwd": str(STUB_18CE)})
    out = capsys.readouterr().out
    assert "/checkbox:init" in out
    assert not out.strip().startswith("{")  # still plain text, not JSON


def test_session_start_silent_when_mode_off(capsys, monkeypatch):
    monkeypatch.setenv("CHECKBOX_MODE", "off")
    session_start._run({"cwd": str(PROJECT_18CE)})
    assert capsys.readouterr().out == ""


def test_session_start_dry_run_end_to_end():
    payload = (REPO_ROOT / "tests" / "fixtures" / "hooks" / "session_start.json").read_text()
    result = subprocess.run(
        [sys.executable, str(BIN), "hook", "session-start"],
        input=payload,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "Odoo change policy" in result.stdout


# -- prompt (UserPromptSubmit) -----------------------------------------------


def test_prompt_emits_compact_reminder_in_full_mode(capsys):
    prompt._run({"cwd": str(PROJECT_18CE)})
    out = capsys.readouterr().out
    assert "checkbox (full)" in out
    assert len(out) <= 400


def test_prompt_silent_in_lite_mode(capsys, monkeypatch):
    monkeypatch.setenv("CHECKBOX_MODE", "lite")
    prompt._run({"cwd": str(PROJECT_18CE)})
    assert capsys.readouterr().out == ""


def test_prompt_silent_without_profile(capsys):
    prompt._run({"cwd": str(STUB_18CE)})
    assert capsys.readouterr().out == ""


# -- subagent_start ------------------------------------------------------------


def test_subagent_start_uses_json_wrapper(capsys):
    subagent_start._run({"cwd": str(PROJECT_18CE), "agent_type": "Explore"})
    out = capsys.readouterr().out
    data = json.loads(out)  # SubagentStart MUST be the JSON form, or it's dropped (§1.7)
    assert data["hookSpecificOutput"]["hookEventName"] == "SubagentStart"
    assert "checkbox" in data["hookSpecificOutput"]["additionalContext"]


def test_subagent_start_silent_in_lite_mode(capsys, monkeypatch):
    monkeypatch.setenv("CHECKBOX_MODE", "lite")
    subagent_start._run({"cwd": str(PROJECT_18CE), "agent_type": "Explore"})
    assert capsys.readouterr().out == ""


def test_subagent_start_dry_run_end_to_end():
    payload = (REPO_ROOT / "tests" / "fixtures" / "hooks" / "subagent_start.json").read_text()
    result = subprocess.run(
        [sys.executable, str(BIN), "hook", "subagent-start"],
        input=payload,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["hookSpecificOutput"]["hookEventName"] == "SubagentStart"


# -- fail-open contract (non-negotiable #4) ----------------------------------


def test_hook_crash_prints_nothing_and_exits_0(monkeypatch, capsys):
    import io

    def _boom(_payload):
        raise RuntimeError("boom")

    from checkbox.hooks.common import safe_main

    monkeypatch.setattr(
        sys, "stdin", io.StringIO("{}")
    )  # give it real stdin so _boom is what raises
    exit_code = safe_main(_boom)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""  # nothing on stdout even on a crash
    assert "boom" in captured.err  # the traceback went to stderr, not swallowed silently
