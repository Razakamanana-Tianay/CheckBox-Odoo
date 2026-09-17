"""Tests for checkbox.mcp_server (P7, optional).

Two groups:
- Lazy-import guarantees, which must pass with the `mcp` SDK absent --
  these are the one test that actually protects CLAUDE.md non-negotiable
  #1 (stdlib-only core except this module, and only lazily).
- The tools themselves, which need the real `mcp` SDK (`pip install
  -e ".[mcp]"`) and are skipped otherwise, same pattern as
  `@pytest.mark.odoo_src` tests skipping without a real Odoo checkout.
  Exercised via `mcp.Client(server)` in-process, per the SDK's own
  documented testing pattern (py.sdk.modelcontextprotocol.io/get-started/
  first-steps/, "Testing" -- no subprocess, no port).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

import pytest  # noqa: E402

STUB_18CE = REPO_ROOT / "tests" / "fixtures" / "stubs" / "odoo18-ce"
RED_OVERRIDE = REPO_ROOT / "tests" / "fixtures" / "diffs" / "move_post_override.py"


def _write_profile(root: Path) -> None:
    (root / ".checkbox").mkdir(parents=True, exist_ok=True)
    (root / ".checkbox" / "profile.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "odoo_version": "18.0",
                "edition": "community",
                "hosting": "on-premise",
                "localizations": [],
                "odoo_source": str(STUB_18CE),
                "enterprise_source": None,
                "custom_addons": [],
                "third_party_addons": [],
                "mode": "full",
                "detected": {},
                "confirmed_by_user": True,
            }
        ),
        encoding="utf-8",
    )


# -- lazy import (no mcp SDK needed / must work without it) -------------------


def test_no_top_level_mcp_import_in_mcp_server_module():
    """Static guard: `import mcp` / `from mcp...` may only appear inside a
    function body (build_server/main), never at module top level -- that is
    the actual lazy-import contract CLAUDE.md non-negotiable #1 requires.
    A dynamic sys.modules-patching test can't check this reliably in this
    suite: pytest.importorskip("mcp") below runs at collection time, before
    any test function body, so the real SDK is already cached by the time a
    test runs -- the subprocess test below is the dynamic complement."""
    import ast

    source = (REPO_ROOT / "plugins" / "checkbox" / "lib" / "checkbox" / "mcp_server.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    for node in tree.body:  # module top level only, not inside function defs
        if isinstance(node, ast.Import):
            names = [n.name.split(".")[0] for n in node.names]
            assert "mcp" not in names, "mcp imported at module top level"
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "mcp", (
                "mcp imported at module top level"
            )


def _system_python_without_mcp() -> str | None:
    import subprocess

    for candidate in ("/usr/bin/python3", "/usr/bin/python3.10", "/usr/bin/python3.12"):
        if not Path(candidate).is_file():
            continue
        probe = subprocess.run([candidate, "-c", "import mcp"], capture_output=True, timeout=10)
        if probe.returncode != 0:  # mcp genuinely absent there
            return candidate
    return None


def test_module_imports_and_reports_missing_sdk_in_a_real_interpreter_without_it():
    """Real black-box check, not a sys.modules simulation: spawn a fresh
    interpreter that genuinely has no `mcp` installed (the system python,
    distinct from this repo's .venv where the `mcp` extra is installed for
    the tests below) and confirm `checkbox.mcp_server` still imports and
    `main()` fails with a clear message instead of a traceback."""
    import subprocess

    python = _system_python_without_mcp()
    if python is None:
        pytest.skip("no system interpreter without the mcp SDK found to test against")

    lib_dir = REPO_ROOT / "plugins" / "checkbox" / "lib"
    script = (
        "import sys; "
        f"sys.path.insert(0, {str(lib_dir)!r}); "
        "import checkbox.mcp_server as mod; "
        "assert hasattr(mod, 'build_server') and hasattr(mod, 'main'); "
        "rc = mod.main(['--root', '.']); "
        "sys.exit(rc)"
    )
    result = subprocess.run([python, "-c", script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 1, result.stderr
    assert "mcp" in result.stderr.lower()


def test_real_mcp_json_invocation_does_not_crash_on_missing_checkbox_module():
    """Regression for the bug the SDK-swapping tests above never caught:
    .mcp.json invokes this file as a bare script (`<python> mcp_server.py
    --root ...`), not via `sys.path.insert` + `import` like every other
    test in this module. Running it that way used to raise
    `ModuleNotFoundError: No module named 'checkbox'`, because Python puts
    the script's own directory (lib/checkbox/) on sys.path[0], not lib/."""
    import subprocess

    script = REPO_ROOT / "plugins" / "checkbox" / "lib" / "checkbox" / "mcp_server.py"
    result = subprocess.run(
        [sys.executable, str(script), "--root", str(REPO_ROOT)],
        input="",
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert "ModuleNotFoundError" not in result.stderr, result.stderr


# -- the tools themselves (needs a real `mcp` SDK install) ---------------------

mcp_sdk = pytest.importorskip("mcp", reason='P7\'s checkbox-mcp needs `pip install -e ".[mcp]"`')

sys.modules.pop("checkbox.mcp_server", None)
from checkbox import mcp_server  # noqa: E402


def _call(root: Path, tool: str, args: dict) -> dict:
    server = mcp_server.build_server(root)

    async def run():
        async with mcp_sdk.Client(server) as client:
            result = await client.call_tool(tool, args)
            return result.structured_content

    return asyncio.run(run())


def test_search_tool_finds_real_indexed_evidence(tmp_path):
    _write_profile(tmp_path)
    result = _call(tmp_path, "search", {"query": "approval", "kind": "source", "limit": 5})
    hits = result["result"] if "result" in result else result
    assert any("po_order_approval" in h["title"] or "Purchase" in h["title"] for h in hits)


def test_classify_tool_flags_the_red_override(tmp_path):
    _write_profile(tmp_path)
    text = RED_OVERRIDE.read_text(encoding="utf-8")
    (tmp_path / "override.py").write_text(text, encoding="utf-8")
    result = _call(tmp_path, "classify", {"path": "override.py"})
    assert result["tier"] == "red"


def test_card_validate_tool_reports_errors_for_a_card_missing_evidence(tmp_path):
    _write_profile(tmp_path)
    card_text = (
        "```checkbox-card\n"
        "id: 0001\n"
        "need: test\n"
        "verdict: config\n"
        "evidence: -\n"
        "status: proposed\n"
        "```\n"
    )
    (tmp_path / "card.md").write_text(card_text, encoding="utf-8")
    result = _call(tmp_path, "card_validate", {"path": "card.md"})
    assert result["valid"] is False
    assert result["errors"]
