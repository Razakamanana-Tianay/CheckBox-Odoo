"""Regression test for the Windows mojibake bug: a hook's stdout pipe can
start out on a non-UTF-8 encoding (e.g. cp1252, the common Windows
locale-preferred encoding for a non-console pipe), which silently mangles
the ladder text's em-dashes. `_write_utf8` must force UTF-8 regardless.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox.hooks import common  # noqa: E402


def test_emit_context_forces_utf8_even_when_stdout_starts_as_cp1252(monkeypatch):
    buf = io.BytesIO()
    wrapper = io.TextIOWrapper(buf, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", wrapper)

    common.emit_context("climb the ladder — skip?")
    wrapper.flush()

    assert buf.getvalue().decode("utf-8") == "climb the ladder — skip?"
