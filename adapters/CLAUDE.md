# adapters: generated files for other agents

Everything in this directory, except this file, is **generated** by `scripts/build_adapters.py` from `plugins/checkbox/rules/`. Don't edit the outputs by hand. Change the rules or the build script, then regenerate.

## Outputs

| File | Host(s) | Copy to (in the user's own project) | Notes |
|---|---|---|---|
| `AGENTS.md` | OpenCode, and (as a bonus) Amp, Jules, Zed, Antigravity, CodeWhale, JetBrains Junie, VS Code+Codex extension, and other `AGENTS.md` readers -- confirmed against a real shipping multi-host plugin (Ponytail's `docs/agent-portability.md`), not guessed | `AGENTS.md` (repo root) | Full ladder rendered with neutral placeholders, plus a CLI section |
| `cursor/checkbox.mdc` | Cursor | `.cursor/rules/checkbox.mdc` | `alwaysApply: true` frontmatter. Verified against cursor.com/docs/context/rules, 2026-09-15 |
| `windsurf/checkbox.md` | Windsurf | `.windsurf/rules/checkbox.md` (still the working path as of 2026-09-15) or `.devin/rules/checkbox.md` (the newer path post Windsurf/Devin AI rebrand -- check which your version reads) | `trigger: always_on` frontmatter. 12,000-char limit per file (rendered ladder is ~2,000 chars). Verified against docs.devin.ai/desktop/cascade/memories |
| `copilot/copilot-instructions.md` | GitHub Copilot | `.github/copilot-instructions.md` | Plain markdown, no frontmatter. Verified against docs.github.com/en/copilot/how-tos/configure-custom-instructions |
| `opencode/README.md` | OpenCode | Not copied -- read in place | Points at `AGENTS.md` + the CLI; OpenCode reads `AGENTS.md` automatically, no separate rule file needed |

**Priority (docs/ARCHITECTURE.md §9):** Claude Code (the real plugin, elsewhere in this repo) first, then OpenCode (this directory's `AGENTS.md`), then the rules-only hosts above. Codex's fuller "plugin hooks" treatment (§9 row 3, the same pattern Ponytail uses) is **deliberately deferred** -- it would need an actual Codex plugin manifest + hook shim, a genuinely bigger lift than a rules file, for a host that (like every non-Claude host) never gets the guard anyway. Revisit if a real user asks for it.

## Rules

- **Generation header.** Every output starts with a comment stating it is generated, the source file, and the source version -- as a real comment (HTML `<!-- -->` for plain markdown, a `#` line *inside* the YAML frontmatter block for Cursor/Windsurf). A bare `#` line outside frontmatter renders as a Markdown H1, not a comment -- confirmed the hard way while building this; `tests/test_build_adapters.py::test_no_comment_lines_render_as_a_heading` guards it.
- **What adapters cannot do.** Non-Claude hosts get the ladder and the CLI instructions only: no guard, no Stop check. Each output says this in one factual sentence (`build_adapters.NO_GUARD_NOTE`), so users don't assume enforcement.
- **Rendering.** Profile-specific placeholders render as instructions to read `.checkbox/profile.json` (or to run `checkbox profile show`), never as baked-in values. `{version}`/`{edition}`/`{studio_clause}` are used as short inline nouns in `ladder.md` (e.g. "may already exist in {version} {edition}") -- their neutral values must stay short phrases too, or the surrounding sentence breaks grammatically (also caught the hard way; see `test_version_and_edition_placeholders_read_grammatically`).
- **Drift check.** `python3 scripts/check_rule_copies.py` must pass. `build_adapters.build()` renders every output in memory (no filesystem writes), so the check is a plain string diff against the committed files here -- no temp directory involved.
- **New hosts.** Add the renderer to `build_adapters.py`, add a row to the table above, and add a drift-check test. Before writing the adapter, verify the host's current rules-file location and format in its official docs (or, failing that, a real shipping multi-host plugin's own adapters -- Ponytail's `docs/agent-portability.md` is a good primary source), and record the URL and verification date in the renderer's docstring.
