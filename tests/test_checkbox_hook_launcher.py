"""Tests for bin/checkbox-hook, the cross-platform Python launcher hooks.json's
shell-form commands invoke (docs/ARCHITECTURE.md D12): skip the Windows Store's
python3 alias stub, fall through py -3, then bare python.

Fully hermetic: each fake "python3"/"py"/"python" is a tiny script that only
prints its own argv, so these run identically on any POSIX machine (including
CI) without needing a real Windows box or a real broken install to reproduce
against. `bin` is always the real, sibling `bin/checkbox` (the launcher derives
it from its own location, not an env var), so assertions match on that real
path rather than needing to fake it too.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = REPO_ROOT / "plugins" / "checkbox" / "bin" / "checkbox-hook"
CHECKBOX_BIN = REPO_ROOT / "plugins" / "checkbox" / "bin" / "checkbox"
BASH = shutil.which("bash") or "/bin/bash"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="drives bash directly")


def _fake_bin(dir_: Path, name: str, body: str) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / name
    # Absolute shebang: the child runs with a PATH restricted to the fake
    # dirs under test, so `#!/usr/bin/env bash` would fail to resolve `bash`.
    path.write_text(f"#!{BASH}\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run(path_dirs: list[Path]) -> subprocess.CompletedProcess:
    env = {"PATH": os.pathsep.join(str(d) for d in path_dirs)}
    return subprocess.run(
        [BASH, str(LAUNCHER), "session-start"],
        env=env,
        input="",
        capture_output=True,
        text=True,
        timeout=5,
    )


def test_skips_the_windows_store_alias_stub(tmp_path):
    windows_apps = tmp_path / "WindowsApps"
    _fake_bin(windows_apps, "python3", 'echo "Python was not found"; exit 1')
    real = tmp_path / "real"
    _fake_bin(real, "python3", 'echo "REAL_PYTHON3 $*"')

    result = _run([windows_apps, real])
    assert "REAL_PYTHON3" in result.stdout
    assert "Python was not found" not in result.stdout


def test_falls_back_to_py_launcher_when_only_the_stub_answers_to_python3(tmp_path):
    windows_apps = tmp_path / "WindowsApps"
    _fake_bin(windows_apps, "python3", 'echo "Python was not found"; exit 1')
    launcher_dir = tmp_path / "launcher"
    _fake_bin(launcher_dir, "py", 'echo "PY_LAUNCHER $*"')

    result = _run([windows_apps, launcher_dir])
    assert "PY_LAUNCHER -3" in result.stdout


def test_falls_back_to_bare_python_as_a_last_resort(tmp_path):
    bare = tmp_path / "bare"
    _fake_bin(bare, "python", 'echo "BARE_PYTHON $*"')

    result = _run([bare])
    assert "BARE_PYTHON" in result.stdout


def test_uses_real_python3_directly_when_nothing_is_wrong(tmp_path):
    real = tmp_path / "real"
    _fake_bin(real, "python3", 'echo "REAL_PYTHON3 $*"')

    result = _run([real])
    assert "REAL_PYTHON3" in result.stdout


def test_python_fallback_also_skips_a_windows_apps_stub(tmp_path):
    windows_apps = tmp_path / "WindowsApps"
    _fake_bin(windows_apps, "python", 'echo "Python was not found"; exit 1')
    real = tmp_path / "real"
    _fake_bin(real, "python", 'echo "REAL_PYTHON $*"')

    result = _run([windows_apps, real])
    assert "REAL_PYTHON" in result.stdout
    assert "Python was not found" not in result.stdout


def test_passes_the_event_name_and_the_real_bin_checkbox_path_through(tmp_path):
    real = tmp_path / "real"
    _fake_bin(real, "python3", 'echo "$*"')

    result = _run([real])
    assert result.stdout.strip() == f"{CHECKBOX_BIN} hook session-start"


def test_end_to_end_with_the_real_interpreter_and_real_checkbox(tmp_path):
    # No fakes at all: drives the real bin/checkbox through the real
    # interpreter this machine already has, the way hooks.json actually will.
    real = Path(shutil.which("python3")).parent
    result = _run([real])
    assert result.returncode == 0
