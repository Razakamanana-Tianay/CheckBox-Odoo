"""checkbox-mcp: exposes search/classify/card_validate to non-Claude hosts.

docs/ARCHITECTURE.md §8.1/§9: "Non-Claude hosts: they get the ladder and
the CLI, but no guard. The P7 MCP server gives them `search`, `classify`
and `card_validate` as tools." This is the one place in the repo allowed
to import a third-party package (repo CLAUDE.md non-negotiable #1) -- and
only lazily, inside `build_server()`/`main()`, never at module import time,
so `python3 -m checkbox.cli` and every hook keep working with the `mcp`
SDK absent. `tests/test_mcp_server.py::test_no_top_level_mcp_import_in_mcp_server_module`
and `::test_module_imports_and_reports_missing_sdk_in_a_real_interpreter_without_it`
guard that.

This module is a thin adapter: it calls the same `checkbox.knowledge.search`,
`checkbox.risk.classify` and `checkbox.card` functions the CLI calls, and
does not reimplement any of their logic.

Verified against the MCP Python SDK's own docs (py.sdk.modelcontextprotocol.io,
"Get started > Connect to a real host" and "Running your server", 2026-09-15):
`from mcp.server import MCPServer`, `@mcp.tool()`, a module-level `mcp` object,
`mcp.run()` under `if __name__ == "__main__":` for stdio. The same docs show
`mcp.Client(mcp)` connecting to the server object in-process for tests --
that is how `tests/test_mcp_server.py` exercises this file's tools without a
subprocess or a real external Odoo MCP server.

Install (not automatic -- network + a third-party dependency, same
"never runs silently" rule §7.2/init skill applies to docs/oca indexes):

    python3 -m venv "$CLAUDE_PLUGIN_DATA/venv"
    "$CLAUDE_PLUGIN_DATA/venv/bin/pip" install "mcp>=2.0,<3"

Registered via plugins/checkbox/.mcp.json, command pointed at that venv's
python. See plugins/checkbox/CLAUDE.md for the exact entry.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    # .mcp.json invokes this file directly as a script, so Python puts
    # this file's own directory (lib/checkbox/) on sys.path[0], not lib/
    # -- `import checkbox` fails without this, same problem bin/checkbox
    # solves for the CLI launcher.
    _LIB = Path(__file__).resolve().parent.parent
    if str(_LIB) not in sys.path:
        sys.path.insert(0, str(_LIB))

from checkbox import card as card_mod
from checkbox import profile as profile_mod
from checkbox.knowledge import search as search_mod
from checkbox.paths import find_project_root
from checkbox.risk import classify as classify_mod


def _load_profile(root: Path) -> profile_mod.Profile:
    try:
        return profile_mod.load(root)
    except FileNotFoundError as exc:
        raise ValueError(
            f"no profile at {root}/.checkbox/profile.json -- run `checkbox profile write` "
            "or the init skill first"
        ) from exc


def _search(root: Path, query: str, kind: str | None, limit: int) -> list[dict[str, Any]]:
    prof = _load_profile(root)
    kinds = kind.split(",") if kind else None
    return search_mod.search(prof, root, query, kinds=kinds, limit=limit)


def _classify(root: Path, path: str, version: str | None) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = root / file_path
    if not file_path.is_file():
        raise ValueError(f"file not found: {file_path}")
    if not version:
        prof = _load_profile(root)
        version = prof.odoo_version or "18.0"
    return classify_mod.classify_file(file_path, version)


def _card_validate(root: Path, path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = root / file_path
    if not file_path.is_file():
        raise ValueError(f"file not found: {file_path}")
    text = file_path.read_text(encoding="utf-8")
    card = card_mod.parse(text)
    profile = None
    try:
        profile = profile_mod.load(root)
    except FileNotFoundError:
        pass
    errors = card_mod.validate(card, profile=profile, raw_text=text)
    return {"valid": not errors, "errors": errors, "verdict": card.get("verdict")}


def build_server(root: Path):
    """Build the MCPServer object. Imports the `mcp` SDK lazily -- this
    function is never called at module import time."""
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    mcp = MCPServer("checkbox")

    @mcp.tool()
    def search(query: str, kind: str = "", limit: int = 10) -> list[dict[str, Any]]:
        """Search the project's Odoo evidence index (source, and docs/oca when built).

        `kind` is a comma-separated filter (e.g. "source" or "source,oca");
        empty means all kinds. Returns Evidence-shaped dicts: kind, ref,
        line, title, snippet, version, score.
        """
        try:
            return _search(root, query, kind or None, limit)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool()
    def classify(path: str, version: str = "") -> dict[str, Any]:
        """Classify a file's blast-radius tier (green/amber/red) with reasons.

        `path` is relative to the project root unless absolute. `version`
        defaults to the project's profile version.
        """
        try:
            return _classify(root, path, version or None)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool()
    def card_validate(path: str) -> dict[str, Any]:
        """Validate a decision card file's internal consistency.

        Returns {valid, errors, verdict}. Does not check or write approvals."""
        try:
            return _card_validate(root, path)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    return mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="checkbox-mcp")
    parser.add_argument(
        "--root",
        default=None,
        help="project root (default: discovered from cwd, same rule as the CLI)",
    )
    args = parser.parse_args(argv)
    root = Path(args.root) if args.root else find_project_root()

    try:
        mcp = build_server(root)
    except ImportError:
        print(
            "checkbox-mcp: the `mcp` SDK is not installed in this interpreter. "
            'Install it with: pip install "mcp>=2.0,<3" (see plugins/checkbox/'
            "lib/checkbox/mcp_server.py's module docstring for the venv setup).",
            file=sys.stderr,
        )
        return 1

    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
