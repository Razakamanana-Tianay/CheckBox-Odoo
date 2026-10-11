"""Regression tests for the guard's trust boundary, found in the 2026-10-11 review.

Every project here is built under `tmp_path`, never a committed fixture:
these tests approve cards and write `.checkbox/` state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox import approvals, card  # noqa: E402
from checkbox import profile as profile_mod  # noqa: E402
from checkbox.hooks import post_edit, pre_bash, pre_edit, stop  # noqa: E402
from checkbox.hooks.common import project_root  # noqa: E402

MODULE_FILE = "addons/mymod/models/x.py"


def _project(tmp_path: Path, mode: str = "strict") -> Path:
    root = tmp_path / "proj"
    (root / "addons" / "mymod" / "models").mkdir(parents=True)
    (root / ".checkbox" / "decisions").mkdir(parents=True)
    (root / ".checkbox" / "profile.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "odoo_version": "18.0",
                "edition": "community",
                "hosting": "on-premise",
                "custom_addons": ["addons"],
                "mode": mode,
            }
        ),
        encoding="utf-8",
    )
    return root


def _write_card(root: Path, addons: str, card_id: str = "0001", tier: str = "green") -> Path:
    path = root / ".checkbox" / "decisions" / f"{card_id}-x.md"
    path.write_text(
        f"# {card_id}\n\n```checkbox-card\nid: {card_id}\nneed: n\n"
        "profile: 18.0 / community / on-premise\nverdict: code\n"
        f"evidence: unverified | none\nsteps: s\naddons: {addons}\n"
        f"extension_point: fields\ntier: {tier}\nupgrade_cost: low\nstatus: proposed\n```\n",
        encoding="utf-8",
    )
    return path


def _edit(root: Path, file_path: str = MODULE_FILE, cwd: Path | None = None) -> dict:
    return {
        "session_id": "s1",
        "cwd": str(cwd or root),
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
    }


def _decision(capsys) -> str | None:
    out = capsys.readouterr().out
    if not out:
        return None
    return json.loads(out)["hookSpecificOutput"].get("permissionDecision", "context")


@pytest.fixture(autouse=True)
def _no_env_mode(monkeypatch):
    monkeypatch.delenv("CHECKBOX_MODE", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)


# -- human-only acts stay human-only in every mode, from every directory ------


@pytest.mark.parametrize("start_mode", ["full", "strict", "lite"])
def test_switching_the_mode_off_does_not_open_a_path_to_self_approval(tmp_path, capsys, start_mode):
    from checkbox import mode as mode_mod

    root = _project(tmp_path, start_mode)
    _write_card(root, "mymod")
    mode_mod.write_local_mode(root, "off")
    pre_bash._run({"cwd": str(root), "tool_input": {"command": "checkbox approve 0001"}})
    assert _decision(capsys) == "deny"
    pre_bash._run(
        {"cwd": str(root), "tool_input": {"command": "cd .checkbox; echo {} > approvals.json"}}
    )
    assert _decision(capsys) == "deny"
    pre_edit._run(_edit(root, ".checkbox/approvals.json"))
    assert _decision(capsys) == "deny"


def test_protected_files_are_denied_from_outside_the_project_too(tmp_path, capsys, monkeypatch):
    root = _project(tmp_path, "strict")
    for name in ("approvals.json", "local.json", "profile.json"):
        pre_edit._run(_edit(root, str(root / ".checkbox" / name), cwd=tmp_path))
        assert _decision(capsys) == "deny", name
    # An addon file named by absolute path while the shell sits elsewhere.
    pre_edit._run(_edit(root, str(root / MODULE_FILE), cwd=tmp_path))
    assert _decision(capsys) == "deny"
    # Stop has no file to anchor on: it falls back to CLAUDE_PROJECT_DIR.
    post_edit._run(_edit(root, str(root / MODULE_FILE), cwd=tmp_path))
    capsys.readouterr()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    assert stop._run({"cwd": str(tmp_path), "session_id": "s1"}) == 2


@pytest.mark.parametrize(
    "command",
    [
        'echo \'{"mode":"off"}\' > .checkbox/local.json',
        "cd .checkbox && rm local.json",
        "sed -i 's/strict/off/' .checkbox/profile.json",
        "python3 -c \"open('.checkbox/local.json','w').write('{}')\"",
    ],
)
def test_strict_denies_shell_writes_to_mode_and_profile_files(tmp_path, capsys, command):
    root = _project(tmp_path, "strict")
    pre_bash._run({"cwd": str(root), "tool_input": {"command": command}})
    assert _decision(capsys) == "deny"
    root = _project(tmp_path / "full", "full")
    pre_bash._run({"cwd": str(root), "tool_input": {"command": command}})
    assert _decision(capsys) is None


def test_repo_root_as_addons_root_still_lets_cards_be_written(tmp_path, capsys):
    root = _project(tmp_path, "strict")
    (root / ".checkbox" / "profile.json").write_text(
        json.dumps({"schema": 1, "odoo_version": "18.0", "custom_addons": ["."], "mode": "strict"}),
        encoding="utf-8",
    )
    (root / "mymod" / "models").mkdir(parents=True)
    pre_edit._run(_edit(root, ".checkbox/decisions/0001-x.md"))
    assert _decision(capsys) is None
    pre_edit._run(_edit(root, "mymod/models/x.py"))
    assert _decision(capsys) == "deny"


# -- card `addons` names modules, the same thing the guard resolves ----------


def test_strict_edit_is_allowed_once_a_code_card_for_the_module_is_approved(tmp_path, capsys):
    root = _project(tmp_path)
    pre_edit._run(_edit(root))
    assert _decision(capsys) == "deny"
    card_file = _write_card(root, "mymod")
    parsed = card.parse(card_file.read_text(encoding="utf-8"))
    assert card.validate(parsed, profile=profile_mod.load(root)) == []
    approvals.approve(root, "0001", approver="tester")
    pre_edit._run(_edit(root))
    assert _decision(capsys) is None


def test_card_addons_must_be_module_names_not_paths(tmp_path):
    root = _project(tmp_path)
    prof = profile_mod.load(root)
    for bad in ("addons/mymod", "../x", "addons"):
        parsed = card.parse(_write_card(root, bad).read_text(encoding="utf-8"))
        assert any("module name" in e for e in card.validate(parsed, profile=prof)), bad


def test_code_card_must_name_at_least_one_addon(tmp_path):
    root = _project(tmp_path)
    parsed = card.parse(_write_card(root, "-").read_text(encoding="utf-8"))
    assert any("addons" in e for e in card.validate(parsed, profile=profile_mod.load(root)))


# -- the agent cannot approve or weaken the guard through file tools ---------


@pytest.mark.parametrize("mode", ["full", "strict"])
def test_write_tool_cannot_touch_approvals_json(tmp_path, capsys, mode):
    root = _project(tmp_path, mode)
    pre_edit._run(_edit(root, ".checkbox/approvals.json"))
    assert _decision(capsys) == "deny"
    pre_edit._run(_edit(root, str(root / ".checkbox" / "approvals.json"), cwd=root / "addons"))
    assert _decision(capsys) == "deny"


@pytest.mark.parametrize("name", ["local.json", "profile.json"])
def test_strict_denies_file_edits_to_mode_and_profile(tmp_path, capsys, name):
    root = _project(tmp_path, "strict")
    pre_edit._run(_edit(root, f".checkbox/{name}"))
    assert _decision(capsys) == "deny"


def test_full_mode_allows_profile_edits(tmp_path, capsys):
    root = _project(tmp_path, "full")
    pre_edit._run(_edit(root, ".checkbox/profile.json"))
    assert _decision(capsys) is None


@pytest.mark.parametrize(
    "command",
    ["checkbox mode set off", "bin/checkbox mode set full --root .", "checkbox profile write"],
)
def test_strict_denies_weakening_the_policy_from_bash(tmp_path, capsys, command):
    root = _project(tmp_path, "strict")
    pre_bash._run({"cwd": str(root), "tool_input": {"command": command}})
    assert _decision(capsys) == "deny"


def test_full_mode_allows_mode_set_and_strict_allows_mode_show(tmp_path, capsys):
    root = _project(tmp_path, "full")
    pre_bash._run({"cwd": str(root), "tool_input": {"command": "checkbox mode set strict"}})
    assert _decision(capsys) is None
    root = _project(tmp_path / "b", "strict")
    pre_bash._run({"cwd": str(root), "tool_input": {"command": "checkbox mode show"}})
    assert _decision(capsys) is None


# -- hooks resolve the project root, not the shell's current directory -------


def test_project_root_walks_up_from_a_subdirectory(tmp_path):
    root = _project(tmp_path)
    assert project_root({"cwd": str(root / "addons" / "mymod")}) == root.resolve()
    assert project_root({"cwd": str(tmp_path)}) == tmp_path.resolve()  # no .checkbox above


def test_strict_guard_survives_a_cd_into_the_addons_dir(tmp_path, capsys):
    root = _project(tmp_path)
    cwd = root / "addons" / "mymod"
    pre_edit._run(_edit(root, "models/x.py", cwd=cwd))  # relative to the new cwd
    assert _decision(capsys) == "deny"
    pre_edit._run(_edit(root, str(root / MODULE_FILE), cwd=cwd))
    assert _decision(capsys) == "deny"


def test_post_edit_and_stop_share_state_across_a_cd(tmp_path, capsys):
    root = _project(tmp_path, "full")
    target = root / MODULE_FILE
    target.write_text("x = 1\n", encoding="utf-8")
    post_edit._run(_edit(root, "models/x.py", cwd=root / "addons" / "mymod"))
    capsys.readouterr()
    assert stop._run({"cwd": str(root), "session_id": "s1"}) == 2
    assert "mymod" in capsys.readouterr().err


# -- approval edge cases ------------------------------------------------------


def test_approve_rejects_ids_that_are_not_four_digits(tmp_path):
    root = _project(tmp_path)
    _write_card(root, "mymod")
    for bad in ("*", "1", "../0001", "0001-x"):
        with pytest.raises(ValueError, match="4-digit"):
            approvals.approve(root, bad, approver="t")


def test_approve_rejects_a_card_whose_block_id_differs_from_its_filename(tmp_path):
    root = _project(tmp_path)
    path = _write_card(root, "mymod")
    path.write_text(path.read_text().replace("id: 0001", "id: 0099"), encoding="utf-8")
    with pytest.raises(ValueError, match="id"):
        approvals.approve(root, "0001", approver="t")


def test_a_card_slug_ending_in_ledger_is_still_a_card(tmp_path):
    root = _project(tmp_path)
    path = _write_card(root, "mymod")
    path.rename(path.with_name("0001-general-ledger.md"))
    assert approvals.approve(root, "0001", approver="t")["card_id"] == "0001"


def test_red_card_needs_a_non_empty_ledger_report(tmp_path):
    root = _project(tmp_path)
    path = _write_card(root, "mymod", tier="red")
    path.write_text(path.read_text().replace("unverified | none", "source | x"), encoding="utf-8")
    report = root / ".checkbox" / "decisions" / "0001-ledger.md"
    report.write_text("  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="ledger"):
        approvals.approve(root, "0001", approver="t")
    report.write_text("1. Balanced moves: OK\n", encoding="utf-8")
    assert approvals.approve(root, "0001", approver="t")["ledger_report"] == "0001-ledger.md"


# -- guard scope --------------------------------------------------------------


def test_guard_handles_absolute_and_dotted_custom_addons_roots(tmp_path, capsys):
    root = _project(tmp_path)
    for value in (str(root / "addons"), "./addons", "addons/"):
        (root / ".checkbox" / "profile.json").write_text(
            json.dumps({"schema": 1, "odoo_version": "18.0", "custom_addons": [value]}),
            encoding="utf-8",
        )
        (root / ".checkbox" / "local.json").write_text('{"mode": "strict"}', encoding="utf-8")
        pre_edit._run(_edit(root))
        assert _decision(capsys) == "deny", value


def test_session_id_cannot_escape_the_session_dir(tmp_path):
    from checkbox import session as session_mod

    root = _project(tmp_path)
    session_mod.record_touched_addon(root, "../../escaped", "mymod")
    assert not (root / "escaped.json").exists()
    assert [p.parent.name for p in root.rglob("*escaped*.json")] == [".session"]


# -- stop ---------------------------------------------------------------------


def test_stop_does_not_block_while_already_continuing_from_a_stop_hook(tmp_path):
    from checkbox import session as session_mod

    root = _project(tmp_path, "full")
    session_mod.record_touched_addon(root, "s1", "mymod")
    payload = {"cwd": str(root), "session_id": "s1"}
    assert stop._run(payload | {"stop_hook_active": True}) == 0
    assert stop._run(payload) == 2


def test_full_mode_stop_is_satisfied_by_a_proposed_card_strict_needs_approval(tmp_path):
    from checkbox import session as session_mod

    for mode, expected in (("full", 0), ("strict", 2)):
        root = _project(tmp_path / mode, mode)
        session_mod.record_touched_addon(root, "s1", "mymod")
        _write_card(root, "mymod")
        assert stop._run({"cwd": str(root), "session_id": "s1"}) == expected, mode


# -- pre-bash heuristics ------------------------------------------------------

_APPROVALS = ".checkbox/approvals.json"


@pytest.mark.parametrize(
    "command",
    [
        "cd .checkbox && echo '{}' > approvals.json",
        f"python3 -c \"open('{_APPROVALS}','w').write('{{}}')\"",
        f"git checkout HEAD~1 -- {_APPROVALS}",
        f"git restore --source=HEAD~1 {_APPROVALS}",
        f"cp /tmp/a.json {_APPROVALS}",
        "psql -c 'update public.account_move set state=1'",
        "psql -c 'UPDATE \"account_move\" SET state=1'",
        "psql -c 'UPDATE ONLY account_move SET x=1'",
        "psql -c 'TRUNCATE account_move_line'",
        "psql -c 'TRUNCATE TABLE stock_quant CASCADE'",
        "psql -c 'DROP TABLE stock_quant'",
        "psql -c 'ALTER TABLE account_move DISABLE TRIGGER ALL'",
        "psql -c 'UPDATE account_payment SET amount=0'",
        "psql -c 'DELETE FROM account_tax'",
        "psql -c 'UPDATE ir_sequence SET number_next=1'",
    ],
)
def test_pre_bash_denies(command):
    assert pre_bash._should_deny(command)[0], command


@pytest.mark.parametrize(
    "command",
    [
        f"cat {_APPROVALS} | jq '.[] | select(.card_id > \"0001\")'",
        f"grep -c hash {_APPROVALS} && echo done > /tmp/x",
        f"git diff {_APPROVALS} > /tmp/approvals.diff",
        f"git add {_APPROVALS} && git commit -m 'card 0007'",
        "psql -c 'SELECT count(*) FROM account_move'",
        "psql -c 'UPDATE res_partner SET name=1'",
    ],
)
def test_pre_bash_allows(command):
    assert not pre_bash._should_deny(command)[0], command


def test_a_corrupt_profile_is_not_a_way_around_the_human_only_checks(tmp_path, capsys):
    root = _project(tmp_path, "strict")
    (root / ".checkbox" / "profile.json").write_text("{ broken", encoding="utf-8")
    pre_edit._run(_edit(root, _APPROVALS))
    assert _decision(capsys) == "deny"
    pre_bash._run({"cwd": str(root), "tool_input": {"command": "checkbox approve 0001"}})
    assert _decision(capsys) == "deny"
