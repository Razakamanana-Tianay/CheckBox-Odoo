# Changelog

Notable changes to `checkbox`, most recent first. Versions follow semver per
`plugins/checkbox/.claude-plugin/plugin.json`; dates are the bump commit's date.

## [1.2.2] - 2026-09-17

### Fixed

- `checkbox doctor` gives an actionable Windows note for `checkbox-mcp`
  (names the real venv path) instead of a silent red MCP banner in `/mcp`.
  `.mcp.json` itself can't be made OS-aware -- Claude Code's MCP config has
  no shell and no per-OS command field -- see `docs/ARCHITECTURE.md` D13.

## [1.2.1] - 2026-09-17

### Fixed

- `checkbox search` no longer crashes on hyphenated or quote-containing
  queries.

### Changed

- Search staleness checks skip `static/`, `i18n/`, `tests/` and migration
  directories (perf).
- Session state writes are atomic; session files older than 30 days are
  pruned automatically.

## [1.2.0] - 2026-09-17

### Added

- `checkbox doctor` detects a Windows Python-launcher stub, `bin/checkbox`'s
  exec bit, and `checkbox-mcp` venv health.
- `checkbox card list` subcommand.
- `checkbox profile detect` hints when a child directory already has a
  profile.

### Fixed

- `mcp_server.py` bootstraps `sys.path` so it runs correctly as a bare
  script -- `checkbox-mcp` was silently broken on every OS, not just
  Windows, before this.
- Hooks force UTF-8 stdout, fixing mangled ladder text on Windows.
- The OpenCode npm plugin gets the same Windows Python-launcher fix as the
  Claude Code hooks.
- The ladder's clarifying question renders as plain text, not a tool call.

## [1.1.1] - 2026-09-16

### Fixed

- Hooks work around the Microsoft Store's placeholder `python3`/`python`
  alias stub on Windows (D12): `hooks.json` switched to shell form calling
  a new `bin/checkbox-hook` launcher that walks `$PATH` by hand.

## [1.1.0] - 2026-09-16

### Added

- `checkbox setup <host>` one-command install for non-Claude hosts
  (OpenCode, Cursor, Windsurf, Copilot).
- Generated OpenCode npm plugin package (`adapters/opencode/`), vendoring a
  verbatim copy of the CLI core.

### Changed

- The hook fast path skips `cli.py`'s full import chain, cutting per-turn
  hook overhead.

## [1.0.0] - 2026-09-15

First tagged release. Ships P1-P8: profile detection, ladder rendering,
decision cards, the deterministic risk classifier and blast-radius guard,
the source evidence index, all 12 seed-case evals, generated adapters for
non-Claude hosts, and the optional `checkbox-mcp` server. README with the
full benchmark table; marketplace listing.

## [0.1.0] - 2026-09-15

Initial plugin skeleton: profile detection and Odoo-source-grounded stubs.
