# checkbox

A Claude Code plugin (plus installable adapters and a ready-to-install npm
plugin for OpenCode, Cursor, Windsurf, GitHub Copilot and other agents) that
makes an AI coding agent walk an **Odoo fit-gap ladder** before it writes any
Odoo code:

> standard → configure → no-code → existing module → code

Each answer is grounded in **evidence** for the project's exact Odoo version,
edition and hosting, recorded as a **decision card**, and every change is
classified by **blast radius** (green / amber / red) with a deterministic
guard that actually blocks in strict mode.

The line it draws:

| Rung | Question |
|---|---|
| 0 | Who does what, when, with which data? (at most one clarifying question) |
| 1 | Can a process change, training or a report filter make the change unnecessary? |
| 2 | **Does the feature already exist in your Odoo version/edition?** |
| 3 | Is it a settings toggle, group, record rule, route, pricelist or template? |
| 4 | Can an automation rule, server action or Studio flow do it (no `.py`)? |
| 5 | Is it an installable module or an OCA app on your branch? |
| 6 | Write code — but only the gap, at the least invasive extension point |

Code is the last resort, not the default answer.

## Install

```bash
# Claude Code: marketplace (plugin lives in this repo)
claude plugin marketplace add checkbox-odoo
claude plugin install checkbox-odoo@checkbox
```

Everything below also works standalone -- the `checkbox` CLI is a single
stdlib-only Python script, no install step:

```bash
plugins/checkbox/bin/checkbox profile detect tests/fixtures/stubs/odoo18-ce --json
plugins/checkbox/bin/checkbox search "purchase approval" --profile tests/fixtures/profiles/18-ce.json --json
plugins/checkbox/bin/checkbox classify tests/fixtures/diffs/move_post_override.py --json
```

**Non-Claude hosts**, one command per host:

```bash
plugins/checkbox/bin/checkbox setup {opencode,cursor,windsurf,copilot} \
    --project /path/to/the/odoo/project --dry-run   # preview first
```

  `checkbox setup` copies the generated rule file into the project (for
  OpenCode it merges into an existing `AGENTS.md` instead of overwriting it).
  Cursor reads `.cursor/rules/checkbox.mdc`, Windsurf reads
  `.windsurf/rules/checkbox.md`, Copilot reads `.github/copilot-instructions.md`.

**OpenCode** can go further than a rules file with the checkbox npm plugin,
which injects the ladder into every session, registers a `checkbox` tool that
shells to a bundled copy of the CLI, and tags written files with their
blast-radius tier:

```bash
opencode2 plugin add checkbox-odoo     # npm; or a file: entry in opencode.json
```

Like every non-Claude path it reminds and classifies -- it cannot deny an
edit.

For hosts that want `search`/`classify`/`card_validate` as MCP tools, the
optional `checkbox-mcp` server is at
`plugins/checkbox/lib/checkbox/mcp_server.py`.

### Windows: "Python was not found" in a hook

The official python.org Windows installer only puts `python.exe` on PATH,
not `python3.exe` -- so on a stock Windows machine the only thing answering
to `python3` is the Microsoft Store's placeholder stub, which prints
"Python was not found; run without arguments to install from the Microsoft
Store..." and exits. As of v1.1.1, checkbox's hooks detect and skip that
stub automatically (falling through `py -3`, then bare `python`) -- this
works whenever Git Bash is installed, which `git` for Windows already gives
you. Hooks fail open either way (your session keeps working even when
nothing usable is found), but the ladder/guard reminders silently do
nothing until Python actually resolves.

If you're on an older version, or a Windows machine with no Git Bash at
all, fix it once:

- Settings > Apps > Advanced app settings > App execution aliases -- turn
  off the `python.exe`/`python3.exe` entries, then reinstall/repair Python
  from python.org with "Add python.exe to PATH" checked; or
- `winget install Python.Python.3.12` (registers `python3` correctly,
  unlike a manual python.org install).

docs/ARCHITECTURE.md's decision log (D12) has the full platform-constraint
writeup for how the automatic fix works and its one remaining gap.

### Windows: running `bin/checkbox` directly from cmd.exe or PowerShell

The commands above (`plugins/checkbox/bin/checkbox ...`) work as-is in Git
Bash, and in WSL, because those shells understand the `#!/usr/bin/env
python3` shebang line. Native `cmd.exe` and PowerShell don't -- and because
the path has directory separators, Windows won't fall back to searching for
a `.cmd`/`.exe` sibling the way it would for a bare command name on `PATH`.
On those shells, put `python3` (or `py -3`) in front of the command:

```powershell
python3 plugins\checkbox\bin\checkbox profile detect ... --json
```

`hooks.json` doesn't have this problem -- it always goes through
`checkbox-hook`, which resolves and `exec`s a real Python itself (D12)
rather than relying on the OS to run `bin/checkbox` as if it were a native
executable.

## How it works

- **`/checkbox:init`** detects the project profile: version, edition, hosting,
  addon paths. Every fact is checked against real Odoo source, not guessed.
- The **ladder** is injected at session start and summarized on every prompt.
- The **guard** denies edits in strict mode when no card approves the change,
  classifies every written file by blast radius, and flags un-carded work on Stop.
- **Red-tier** changes require a human `checkbox approve` — a card is a
  decision, but it never approves itself.

## Benchmark

Eval results against the 12 seed cases (`claude plugin eval`, real runs,
2026-09-15). Scores are pass rate on the case's ground-truth verdict. 11/12
cases score 1.0. `docs/ARCHITECTURE.md` §13 P5 holds the full scorecard.

| Case | Request | Expected verdict | Score |
|---|---|---|---|
| `po-approval-threshold` | Purchase orders above a threshold need manager approval | config | 1.0 |
| `bill-ref-required` | Vendor bills can't post without a vendor reference | nocode | 1.0 |
| `dropship` | Vendor ships directly to the customer | standard/module | 1.0 |
| `serial-tracking` | Serial number field on stock moves | config | 1.0 |
| `so-line-margin` | Margin field on sale order lines | module | 1.0 |
| `tax-rounding-per-line` | Round tax per line instead of per order | config | 1.0 |
| `port-of-loading` | Add Port of Loading on quotations and print it | code (green) | 1.0 |
| `sql-fix-posted-lines` | SQL update to change account on posted journal items | red — use the standard path | 1.0 |
| `online-python-field` | Add a field on partners | nocode (Studio) | 1.0 |
| `quality-check-ce` | Block picking validation until a quality check is done | code (red) | 1.0 |
| `quality-check-ee` | Same, on Enterprise | config/nocode | 0.67→1.0* |
| `ambiguous-need` | "Customers should get reminders" | one clarifying question, no card | 0.5** |

\* Enterprise-only; the exact blocking mechanism is `TODO(verify)` — no
Enterprise source available. Noise between runs is expected and kept.

\*\* A genuine, reproducible finding, kept rather than loosening the rubric:
the agent asks three clarifying questions against the ladder's explicit
"at most one".

## Credits

`checkbox` borrows **Ponytail**'s delivery pattern — a hook-injected ruleset,
intensity levels, adapters for many agents, and a with/without benchmark —
but not its text. The two answer different questions and compose:
Ponytail decides *how little* code to write once the answer is "code";
checkbox decides whether the answer should be code at all.

## License

MIT. See `LICENSE`.