# adapters: generated files for other agents

Everything in this directory, except this file, is **generated** by `scripts/build_adapters.py` from `plugins/fitgate/rules/`. Don't edit the outputs by hand. Change the rules or the build script, then regenerate.

## Outputs

| File | Host(s) | Notes |
|---|---|---|
| `AGENTS.md` | OpenCode, Codex, Amp, Jules and other AGENTS.md readers | Full ladder rendered with neutral placeholders, plus "run `fitgate profile show` to read this project's profile" |
| `cursor/fitgate.mdc` | Cursor | Always-apply rule |
| `windsurf/fitgate.md` | Windsurf | Workspace rule |
| `copilot/copilot-instructions.md` | GitHub Copilot editors | Instruction-only |
| `opencode/README.md` | OpenCode | How to point `opencode.json` at the CLI and AGENTS.md |

**Priority:** OpenCode first, then Codex, then the rules-only hosts.

## Rules

- **Generation header.** Every output starts with a one-line comment stating it is generated, the source file, and the source version.
- **What adapters cannot do.** Non-Claude hosts get the ladder and the CLI instructions only: no guard, no Stop check. Each output says this in one factual sentence, so users don't assume enforcement.
- **Rendering.** Profile-specific placeholders render as instructions to read `.fitgate/profile.json` (or to run `fitgate profile show`), never as baked-in values.
- **Drift check.** `python3 scripts/check_rule_copies.py` must pass. It re-renders into a temp directory and diffs against this directory.
- **New hosts.** Add the renderer to `build_adapters.py`, add a row to the table above, and add a drift-check test. Before writing the adapter, verify the host's current rules-file location and format in its official docs, and record the URL in the renderer's docstring.
