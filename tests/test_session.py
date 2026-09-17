"""Tests for checkbox.session: atomic save, and stale-file pruning."""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox import session as session_mod  # noqa: E402
from checkbox.hooks import session_start  # noqa: E402


def test_save_then_load_roundtrips(tmp_path):
    session_mod.save(tmp_path, "abc", {"touched_addons": ["purchase_x"]})
    state = session_mod.load(tmp_path, "abc")
    assert state["touched_addons"] == ["purchase_x"]


def test_save_does_not_leave_a_tmp_file_behind(tmp_path):
    session_mod.save(tmp_path, "abc", {"touched_addons": []})
    session_dir = tmp_path / ".checkbox" / ".session"
    assert [p.name for p in session_dir.iterdir()] == ["abc.json"]


def test_prune_stale_removes_old_sessions_only(tmp_path):
    session_dir = tmp_path / ".checkbox" / ".session"
    session_dir.mkdir(parents=True)
    old = session_dir / "old.json"
    fresh = session_dir / "fresh.json"
    old.write_text("{}")
    fresh.write_text("{}")

    old_time = time.time() - 40 * 24 * 60 * 60  # 40 days ago
    import os

    os.utime(old, (old_time, old_time))

    removed = session_mod.prune_stale(tmp_path)
    assert removed == 1
    assert not old.exists()
    assert fresh.exists()


def test_prune_stale_on_missing_dir_is_a_noop(tmp_path):
    assert session_mod.prune_stale(tmp_path) == 0


def test_session_start_hook_prunes_stale_sessions(tmp_path, capsys):
    import os

    session_dir = tmp_path / ".checkbox" / ".session"
    session_dir.mkdir(parents=True)
    old = session_dir / "old.json"
    old.write_text("{}")
    old_time = time.time() - 40 * 24 * 60 * 60
    os.utime(old, (old_time, old_time))

    session_start._run({"cwd": str(tmp_path)})
    capsys.readouterr()  # no assertion on the ladder text itself, just the side effect

    assert not old.exists()
