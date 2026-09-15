# checkbox

A Claude Code plugin (plus adapters for OpenCode, Codex, Cursor, Windsurf and
other agents) that makes an AI coding agent walk an **Odoo fit-gap ladder**
before it writes any Odoo code:

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
# marketplace (plugin lives in this repo)
claude plugin marketplace add checkbox-odoo
claude plugin install checkbox-odoo@checkbox
```

The plugin's `bin/checkbox` CLI also works standalone, without Claude Code:

```bash
plugins/checkbox/bin/checkbox profile detect tests/fixtures/stubs/odoo18-ce --json
plugins/checkbox/bin/checkbox search "purchase approval" --profile tests/fixtures/profiles/18-ce.json --json
plugins/checkbox/bin/checkbox classify tests/fixtures/diffs/move_post_override.py --json
```

For non-Claude hosts, a `checkbox-mcp` server exposes `search`, `classify`
and `card_validate` as MCP tools (see `plugins/checkbox/lib/checkbox/mcp_server.py`).

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