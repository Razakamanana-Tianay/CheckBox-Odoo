# plugins/checkbox: the Claude Code plugin

This file is for checkbox developers. Claude Code does not load a plugin-root `CLAUDE.md` as context for plugin users, so nothing here reaches end users. Anything users' agents must know goes into `rules/` (injected by hooks) or into a skill.

## Layout contract

```
.claude-plugin/plugin.json   ← only file inside .claude-plugin/
bin/checkbox                  ← executable launcher; adds ../lib to sys.path, calls checkbox.cli:main
lib/checkbox/                 ← core package
rules/                       ← ladder.md, ladder.compact.md, hosting.json, risk/*.json
skills/<name>/SKILL.md       ← ladder, init, card, review, mode, help
agents/<name>.md             ← standard-scout, ledger-reviewer
hooks/hooks.json
evals/                       ← claude plugin eval suite
```

- Every component directory sits at the plugin root, never inside `.claude-plugin/`.
- Every path in `plugin.json` and `hooks.json` is relative and starts with `./`, or uses `${CLAUDE_PLUGIN_ROOT}`.
- Nothing may point outside this directory.

## plugin.json

- **Fields:** keep `name` (`checkbox`), `displayName`, `version`, `description`, `author`, `repository`, `license` (`MIT`) and `keywords`.
- **Versioning:** bump `version` on every user-visible change.
- **Evals path:** only add `experimental.evals` if the suite moves away from `evals/`.
- **Validation:** run `claude plugin validate .` from this directory; it must exit 0. Don't add `--strict`: it turns the "CLAUDE.md at the plugin root isn't loaded for installed users" warning (line 3 above) into a failure, and that warning is accepted by design, not a defect to fix. Verified 2026-09-15: without `--strict`, `claude plugin validate` exits 0 with that warning still printed; `--strict` alone makes it exit 1.

## hooks/hooks.json

- Exec form only: `"command": "python3"`, `"args": ["${CLAUDE_PLUGIN_ROOT}/bin/checkbox", "hook", "<event>"]`.
- Set an explicit `timeout` (seconds) on each handler: 5 for injection hooks, 5 for guards.
- **Event → subcommand mapping** (keep it in sync with `lib/checkbox/hooks/`):

  | Event | Matcher | Subcommand |
  |---|---|---|
  | `SessionStart` | `startup\|resume\|clear\|compact` | `session-start` |
  | `UserPromptSubmit` | — | `prompt` |
  | `SubagentStart` | — | `subagent-start` |
  | `PreToolUse` | file-edit tools (see platform-facts) | `pre-edit` |
  | `PreToolUse` | `Bash` | `pre-bash` |
  | `PostToolUse` | file-edit tools | `post-edit` |
  | `Stop` | — | `stop` |

- **After editing:** `/reload-plugins` in the running session, then check `/hooks` shows the entries as "Plugin Hooks".
- **Before changing any output shape:** re-read the event's section of the hooks reference, then update `docs/notes/platform-facts.md`.

## Skills

- **Frontmatter:** always set `name` explicitly; without it, marketplace installs fall back to a version-string directory name.
- **User-only skills:** `init`, `mode` and `help` use `disable-model-invocation: true`.
- **Descriptions:** each description decides routing and costs always-on tokens.
  - One or two sentences.
  - Concrete trigger phrases: "add a field", "custom module", "override", "Odoo customization".
  - No marketing.
  - Re-run `claude plugin details checkbox` after changing any description.
- **Context:** skill bodies can reference `${CLAUDE_PLUGIN_ROOT}/rules/...` and supporting files (`extension-points.md`, `hosting.md`, `card-template.md`) that load on demand. Keep `SKILL.md` short and push detail into those files.
- **Shared text:** skills must not restate the ladder. They point to it, or ask the CLI to render it (`checkbox ladder render --level full`).
- **`card`:** instructs the agent to delegate evidence gathering to `checkbox:standard-scout`, then write `.checkbox/decisions/NNNN-slug.md` with `status: proposed`. It validates with `checkbox card validate <file>` before finishing.
- **`init`:** runs `checkbox profile detect --json`, then asks the user to confirm or correct one field at a time (version, edition, hosting, source paths, custom addon paths). It then writes the profile with `checkbox profile write` and builds the source index. It offers the docs and OCA indexes as optional, and never runs them silently (network + disk).

## Agents

- **`standard-scout`**
  - Configuration: `disallowedTools: Write, Edit`, `model: sonnet`, `maxTurns: 15`.
  - Prompt: return evidence items only (`kind | ref | why it answers the rung`); stop at the first rung proven; say `unverified` when nothing is found.
- **`ledger-reviewer`**
  - Configuration: `disallowedTools: Write, Edit`, `model: opus`.
  - Prompt: a fixed checklist covering balanced moves, rounding and currency, multi-company, valuation layers, reversals/credit notes, sequences/gaps, access and `sudo`, upgrade exposure. Output is a Markdown report the `review` skill appends to the card.
- **Allowed frontmatter:** plugin agents cannot declare `hooks`, `mcpServers` or `permissionMode`; don't try.

## Manual smoke test

```bash
mkdir -p /tmp/fg-smoke && cp -r ../../tests/fixtures/projects/18-ce/. /tmp/fg-smoke/
cd /tmp/fg-smoke && claude --plugin-dir <repo>/plugins/checkbox
```

What's testable after P3, honestly:

1. `/checkbox:init` → the profile is confirmed. (P2: works)
2. "Write a module so purchase orders above 5000 need manager approval" →
   the ladder skill should delegate to `standard-scout`, which runs
   `checkbox search` and finds the real `po_order_approval` settings field
   and its settings-view help text ("Request managers to approve orders
   above a minimum amount") -- both are indexed and searchable as of P3.
   The card skill should then draft a card with `verdict: config` and real
   `source` evidence citing those two hits, and `card validate` should
   accept it. If evidence still comes back `unverified`, that's a
   regression to investigate, not the expected P3 outcome.
3. `/checkbox:mode strict`, then "add a field on sale orders" without a
   card → **not testable until P4**: there is no PreToolUse guard yet, so
   nothing will deny the edit. Confirm instead that `/checkbox:mode strict`
   itself round-trips (`checkbox mode show` reflects it) and that the
   ladder skill still recommends drafting a card first, on discipline
   alone, not enforcement.
