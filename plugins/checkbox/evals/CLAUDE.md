# evals: `claude plugin eval` suite

This suite is the product's proof. The with/without Δ is the number published in the README and on LinkedIn, so expectations are ground truth, not guesses.

This file describes what P5 actually built (rewritten 2026-09-15; the original version described a `scripts/build_eval_fixtures.py` + `fixture/` design that was decided against -- see docs/ARCHITECTURE.md §13's P5 row for why).

## Format (Claude Code v2.1.269+)

```
evals/
├── <case>/
│   ├── prompt.md          # frontmatter: max_turns, timeout_seconds, allowed_tools, tags; body = user prompt
│   ├── case.yaml          # schema_version "1.1", name, description (ground truth + citation), context.scaffold_script
│   ├── scaffold.sh        # copies a tests/fixtures/stubs/<tree> into the empty workspace, writes .checkbox/profile.json
│   └── graders/*.md       # one grader per file
└── results/               # gitignored (**/evals/results/ in .gitignore -- note the leading **/, this dir is not at repo root)
```

There is no `fixture/` directory and no generator script. Each case's `scaffold.sh` copies straight from the repo's own `tests/fixtures/stubs/<odoo-tree>` (the same hand-written, real-source-verified mimics `tests/` already uses) into the empty eval workspace, and writes `.checkbox/profile.json` inline. A stub tree shared by unit tests and eval cases is a feature, not a workaround: one place to keep in sync with real Odoo source, one set of header comments citing what was verified and when.

- **Environment.** Each run starts in an empty workspace, with no user settings, no CLAUDE.md and no other plugins. Anything the case needs must come from `scaffold.sh` (runs only with `--scaffold`) or from the prompt.
- **Environment variables.** Only `EVAL_*` variables reach the run. Don't rely on anything else.
- **`bin/` is on `PATH`.** Every skill/agent prompt can call bare `checkbox ...` from Bash -- verified against `code.claude.com/docs/en/plugins-reference` (platform-facts.md §3.5). `checkbox search`, `checkbox card next-id`, etc. all need `Bash` granted at the top-level run (`--allow-tools ... Bash`), not just `Write`/`Edit` -- every case's ladder→card flow shells out to the CLI.
- **`scaffold_script` finds its own directory via `$0`.** It runs as you (normal shell env, not the filtered `EVAL_*`-only allowlist the agent gets), in the empty workspace, before Claude starts. No cwd/env-discovery helper is needed (platform-facts.md §3.1).
- **mode stays `full` in every `scaffold.sh`.** `strict` would make `PreToolUse` deny addon writes mechanically, which would make a trap case's "zero writes" grader pass regardless of whether the ladder actually persuaded the agent -- that measures the guard, not the ladder, and would make Δ meaningless. The guard's mechanical enforcement is already covered deterministically (no paid model calls) by `tests/test_hooks_guard.py`.

## Writing a case

1. **Prompt.** Phrase it the way a developer would, usually asking for code. Trap cases *should* tempt the agent to write a module. Never mention checkbox, ladders or cards in the prompt. Make it concrete enough that rung 0 ("at most one clarifying question... don't default to asking when a reasonable reading exists") doesn't legitimately trigger a question before the card -- an underspecified prompt (e.g. "adds a field on contacts" with no purpose given) got a *correct* clarifying question instead of a card in real runs, which is good agent behavior but a bad case design.
2. **Profile.** `scaffold.sh` copies a `tests/fixtures/stubs/<tree>` (`odoo17-ce`, `odoo18-ce`, `odoo18-ee`) into `./odoo-src` and writes `.checkbox/profile.json` (version/edition/hosting fixed, `mode: full`, `custom_addons: ["addons"]`, `odoo_source: "odoo-src"`). Name the case after the need and suffix the variant (`quality-check-ce`, `quality-check-ee`).
3. **Stub content.** If a case needs an evidence field or a model that isn't already in `tests/fixtures/stubs/`, add it there (not to a case-local fixture), following the existing convention: a header comment citing the real file, branch, source URL and verification date. Never hand-write content that claims to be Odoo source without checking it against a real checkout first (repo CLAUDE.md non-negotiable #3). Confirm it's actually searchable with `checkbox search "<term>" --profile <a profile.json pointing at the stub>` before wiring it into a case.
4. **Graders.**
   - **Card fields:** `regex` with `target: trace` (not `last_message` -- the card is written to a file via `Write`, and `trace` sees every message in the run, `regex` graders see it uncompressed), e.g. `pattern: "verdict:\\s*config"`. When §11.3 gives an allowed set rather than one verdict, match it with alternation (`verdict:\\s*(config|module)`), don't pick one arbitrarily.
   - **Trap cases (config/module cases expecting zero addon writes):** `tool_used` on `Write`, `input_match` scoped to the addon root (`"\"file_path\"\\s*:\\s*\"addons/"`), `min: 0, max: 0`. Leave `arm` unset -- per platform-facts.md §3.6, auto-exclusion from two-arm scoring applies only to `tool: Skill` graders; a `Write`-targeted grader is already scored in both arms by default, which is what makes its Δ meaningful.
   - **`tool_used` `input_match` is a plain JS regex, no inline flags.** `(?i)` is not supported (confirmed the hard way: a grader using it throws at run time, `flags:` isn't a documented `tool_used` option either -- only `regex` graders take `flags`). Write both cases into an alternation or a character class instead.
   - **Steps/extension-point correctness:** an `llm` grader with explicit PASS/FAIL lines, `focus: trace` when it needs to see reasoning that predates the final card, kept short.
   - **Indicator only:** one `tool_used: Skill` grader per case (`input_match` on `"checkbox:ladder"`) so a report immediately shows whether the ladder skill fired at all -- it's free and automatically excluded from scoring in two-arm runs.
5. **Record the ground truth.** `case.yaml`'s `description` holds the expected verdict/tier and exactly what was checked to confirm it -- a real-source path and verification date, a `tests/risk/test_classify.py`/`tests/test_hooks_guard.py` test name when the expectation is a claim about checkbox's own deterministic behaviour rather than about Odoo, or an explicit `TODO(verify)` with why (e.g. Enterprise source unavailable, no license) when it can't be fully confirmed -- grade only the part that was actually confirmed in that case. See docs/ARCHITECTURE.md §11.3 for the full table.

## Running

```bash
# free structural check -- validates every case.yaml/prompt.md/grader loads, $0 spent
claude plugin eval plugins/checkbox --runs 1 --ablation none --max-cost-usd 0 --json /tmp/check.json

# iterate on one case, one arm, one run (needs socat + bubblewrap on Linux for the Bash sandbox)
claude plugin eval plugins/checkbox --case '<case>' --runs 1 --ablation none --scaffold --allow-tools Write Edit Bash --trust-plugin

# debug a low score: --keep-temp preserves the run's sandbox (chmod 700 the kept dir and its sealed/ subdir to read it)
claude plugin eval plugins/checkbox --case '<case>' --runs 1 --ablation none --scaffold --allow-tools Write Edit Bash --keep-temp --json /tmp/debug.json

# full suite with baseline (costs real money; cap it)
claude plugin eval plugins/checkbox --scaffold --allow-tools Write Edit Bash --no-publish --max-cost-usd 15 --json docs/benchmarks/latest.json

# CI gate (pin models so scores are comparable)
claude plugin eval plugins/checkbox --trust-plugin --scaffold --allow-tools Write Edit Bash \
  --threshold 0.8 --model <pinned-model> --judge-model <pinned-judge> --no-publish --max-cost-usd 20 --json results.json
```

## Reading results

- **Δ ≈ 0 with the process grader failing:** the ladder did not trigger. Check the SessionStart injection before touching skill descriptions.
- **Negative Δ with the correct card in the transcript:** suspect the `llm` judge. Re-run with `--judge-model sonnet` and tighten the rubric.
- **A run with implausibly few turns (1-2) and no error:** grep its trace for `"session limit"` before trusting the score -- a usage-limit hit mid-run scores 0 without marking the run `partial` (confirmed: `bill-ref-required` scored 0.25 this way once, 1.0 on a clean re-run).
- **`apply-seccomp: ... nested userns is capability-restricted` in a Bash tool_result:** the eval's Bash sandbox (bubblewrap) can't nest inside this machine's own sandboxing. Not a plugin bug -- the agent should fall back to `Glob`/`Grep`/`Read` against the copied stub tree and can still complete the ladder→card flow, just more slowly and at higher cost. If every case in a run hits this, the run's signal is degraded but not meaningless (a with/without comparison is still informative if both arms are affected equally).
- **Usage-limit errors:** they score 0 without marking the run partial. Check `NOTES` before believing a regression.
- **Archiving:** copy the final `aggregate-result.json` from a *full-suite* run to `docs/benchmarks/<date>-<model>.json`. Don't archive single-case iteration runs there -- that directory is the published benchmark, not a scratch log.

## A note on concurrent sessions

If more than one Claude Code session works on this repo at once, they share the same working tree and `.git` -- there's no isolation between them. If you're about to make a structural decision here (add/remove a generation mechanism, change the fixture format), check `git log --oneline -10` and `git status` first; a stale plan in your own context can look current when it isn't.
