# checkbox

checkbox is a Claude Code plugin (plus adapters for other agents) that makes coding agents walk an **Odoo fit-gap ladder** before writing Odoo code:

standard → configure → no-code → existing module → code.

It also makes them:

- ground each answer in evidence for the project's exact version, edition and hosting;
- record a decision card;
- classify changes by blast radius: green, amber or red.

The full design is in `docs/ARCHITECTURE.md`. Read it before any structural change. Section numbers below (§) refer to that file.

## Non-negotiables

1. **The core is stdlib-only Python ≥ 3.10.**
   - No third-party imports anywhere under `plugins/checkbox/lib/checkbox/`, except the optional MCP module (P7), which must import lazily.
   - Dev tools (pytest, ruff) live in `pyproject.toml` only.
2. **Deterministic first.** Profile detection, card validation, risk tiering and guards are plain code with tests. Never delegate these to an LLM prompt.
3. **No Odoo fact without a source.**
   - A model, method, module, setting or menu path added to `rules/`, `skills/`, `evals/` or tests must be checked against real Odoo source or the official documentation for that version.
   - For risk rules, this means `checkbox rules verify`.
   - If you cannot verify a fact, write `TODO(verify)` and say so. Do not guess.
4. **Hooks are fast and fail-open.**
   - p95 ≤ 150 ms. No index loading inside hooks.
   - A hook crash must print nothing to stdout and exit 0, logging to stderr. The one exception is the strict-mode guard, which denies with an explanation.
5. **Budgets** (checked by tests):
   - always-on context ≤ 1,000 tokens;
   - SessionStart `additionalContext` ≤ 6,000 chars;
   - per-prompt reminder ≤ 400 chars;
   - hook output cap is 10,000 chars.
6. **Injected text is factual.** Phrase it as project policy ("This project uses…", "Cards are created with status proposed"), never as fake system commands.
7. **Single source of truth.**
   - The ladder text lives only in `plugins/checkbox/rules/ladder.md` and `ladder.compact.md`.
   - Skills, hooks and adapters render from it. `adapters/` is generated; never hand-edit it.
8. **YAGNI applies to this repo too.** No option, flag or abstraction ships without a test or eval case that needs it.

## Repo map

```
CLAUDE.md                       ← you are here
docs/ARCHITECTURE.md            ← design, plan, decisions, open questions
docs/notes/platform-facts.md    ← verified Claude Code facts (P0 output)
.claude-plugin/marketplace.json ← this repo is also a marketplace
plugins/checkbox/               ← the plugin (see its CLAUDE.md)
  lib/checkbox/                 ← core package (see its CLAUDE.md)
  rules/                        ← ladder text + risk data (see its CLAUDE.md)
  skills/ agents/ hooks/ bin/
  evals/                        ← claude plugin eval suite (see its CLAUDE.md)
adapters/                       ← generated files for other agents (see its CLAUDE.md)
scripts/                        ← build_adapters.py, check_rule_copies.py
tests/                          ← pytest; fixtures/stubs are tiny fake Odoo trees
```

## Commands

```bash
# setup (dev tools only)
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

# fast checks: run before every commit
ruff check . && ruff format --check .
pytest -q
claude plugin validate plugins/checkbox   # no --strict: the plugin-root CLAUDE.md warning is accepted by design, see its own header
claude plugin validate . --strict
python3 scripts/check_rule_copies.py

# core CLI (works without Claude Code)
plugins/checkbox/bin/checkbox doctor
plugins/checkbox/bin/checkbox profile detect tests/fixtures/stubs/odoo18-ce --json
plugins/checkbox/bin/checkbox search "purchase approval" --profile tests/fixtures/profiles/18-ce.json --json
plugins/checkbox/bin/checkbox classify tests/fixtures/diffs/move_post_override.py --json
plugins/checkbox/bin/checkbox rules verify --version 18.0 --odoo-src "$ODOO18_SRC"

# hook dry-runs (stdin payloads in tests/fixtures/hooks/)
# SessionStart/UserPromptSubmit print plain text (platform-facts.md §1.6), not JSON:
plugins/checkbox/bin/checkbox hook session-start < tests/fixtures/hooks/session_start.json
# SubagentStart and PreToolUse (P4) use the hookSpecificOutput JSON form:
plugins/checkbox/bin/checkbox hook subagent-start < tests/fixtures/hooks/subagent_start.json | python3 -m json.tool
plugins/checkbox/bin/checkbox hook pre-edit < tests/fixtures/hooks/pre_edit_strict_no_card.json | python3 -m json.tool

# run the plugin interactively (development)
claude --plugin-dir plugins/checkbox
#   after editing hooks/agents/.mcp.json inside a session: /reload-plugins
#   SKILL.md edits apply immediately

# token cost of the plugin
claude plugin details checkbox

# evals: cheap iteration, then full run (real model calls, costs money)
# Bash is required, not optional: every skill invokes the checkbox CLI
# through it (bin/ is on PATH automatically while the plugin is enabled --
# verified 2026-09-15). Bash needs the sandbox backend (bwrap + socat on
# Linux); without it Claude Code refuses each Bash-granted run.
claude plugin eval plugins/checkbox --case 'po-*' --runs 1 --ablation none --scaffold --allow-tools Write Edit Bash
claude plugin eval plugins/checkbox --allow-tools Write Edit Bash --scaffold --no-publish --max-cost-usd 15
```

`$ODOO17_SRC`, `$ODOO18_SRC` and `$ODOO19_SRC` point to local checkouts of Odoo Community on those branches. `$ODOO18_EE_SRC` points to Enterprise, if available. Tests that need them are marked `@pytest.mark.odoo_src` and skip when the variable is unset.

## Workflow: explore → plan → implement → verify

0. **Orient.** Before anything else, read `docs/notes/status.md` for the current phase and any settled-but-not-obvious decisions, then `git log --oneline -15` and `git status` — if either shows activity you don't recognize, another session may be active on this repo (check with a multi-session tool if you have one); investigate and reconcile before building on top of it, don't guess or silently overwrite. This step exists because skipping it once caused two sessions to build incompatible designs for the same subsystem (docs/notes/status.md has the full story).
1. **Explore.** Read the relevant section of `docs/ARCHITECTURE.md` and the nested `CLAUDE.md` of the area you touch. For anything about Claude Code behaviour, read `docs/notes/platform-facts.md` first. If the fact is not there, verify it at https://code.claude.com/docs (plugins-reference, hooks, plugin-evals, skills, sub-agents) and add it to that file with the link and date.
2. **Plan.** State the files to change, the tests to add, and the check command that proves it. Keep the change inside one phase of the plan (§13).
3. **Implement.** Write the test first when the behaviour is deterministic.
4. **Verify.** Run the phase's check commands (§13) plus the fast checks above. Paste the command output summary in your final message. Never claim "done" without it.

## Conventions

- **Python.**
  - Type hints everywhere; `from __future__ import annotations`.
  - `pathlib`; `json` for all config and data.
  - No global state; functions take explicit paths.
  - Parse Odoo files with `ast` and `xml.etree.ElementTree`. Never import Odoo, and never execute project code.
- **CLI contract.**
  - Every subcommand supports `--json`.
  - Exit codes: 0 ok, 1 check failed, 2 usage or environment error.
  - Human output goes to stdout and diagnostics to stderr.
- **Plugin files.**
  - kebab-case names; skills under `skills/<name>/SKILL.md` with frontmatter `name` set explicitly.
  - Hooks in exec form: `"command": "python3"`, `"args": ["${CLAUDE_PLUGIN_ROOT}/bin/checkbox", "hook", "<event>"]`.
- **Language.** English for code, docs, skills and injected text. Odoo terms stay as Odoo writes them (`res.config.settings`, `account.move`).
- **Commits.** Conventional Commits (`feat(risk): …`, `fix(hooks): …`). One phase per PR.
- **Versioning.** Semver in `plugins/checkbox/.claude-plugin/plugin.json`. Bump it on every user-visible change; users only get updates on a bump.

## Definition of done

- The phase check commands and the fast checks pass, with output shown.
- New Odoo facts are verified (source path or doc URL recorded next to the fact).
- Budgets are respected (the tests in `tests/test_budgets.py` pass).
- If the ladder text changed, `python3 scripts/build_adapters.py` has been run and the drift check passes.
- If behaviour visible to the agent changed, the relevant eval cases have been run at least once with `--runs 1`.
- `docs/ARCHITECTURE.md` has been updated if a decision (§14) or a contract (§5, §6, §8.2) changed.

## Don't

- Don't add dependencies to the core, or vendor Ponytail's rule text. We follow its pattern and credit it in the README; its text is not ours.
- Don't let the agent approve cards, or write `.checkbox/approvals.json`, by any path.
- Don't store client code, client data or built indexes in this repo or in the plugin directory.
- Don't reference files outside `plugins/checkbox/` from plugin components. Claude Code rejects paths that escape the plugin root, and marketplace installs don't copy them.
- Don't put runtime state in `${CLAUDE_PLUGIN_ROOT}`; it changes on every update. Use `${CLAUDE_PLUGIN_DATA}` (via `CHECKBOX_DATA_DIR` resolution) or the project's `.checkbox/`.
- Don't use exit code 1 to block in hooks; it does not block. Use JSON `permissionDecision: "deny"` (PreToolUse) or the documented Stop decision.
- Don't write eval expectations from memory. They are ground truth and must be confirmed against source.
