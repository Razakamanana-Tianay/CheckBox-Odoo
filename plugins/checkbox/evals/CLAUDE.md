# evals: `claude plugin eval` suite

This suite is the product's proof. The with/without Δ is the number published in the README and on LinkedIn, so expectations are ground truth, not guesses.

## Format (Claude Code v2.1.269+)

```
evals/
├── <case>/
│   ├── prompt.md          # frontmatter: max_turns, timeout_seconds, allowed_tools, tags; body = user prompt
│   ├── case.yaml          # schema_version "1.1", name, context.scaffold_script, context.add_dirs
│   ├── scaffold.sh        # writes .checkbox/profile.json + Odoo slice into the empty workspace
│   ├── fixture/           # per-case copy produced by scripts/build_eval_fixtures.py
│   └── graders/*.md       # one grader per file
└── results/               # gitignored
```

- **Environment.** Each run starts in an empty workspace, with no user settings, no CLAUDE.md and no other plugins. Anything the case needs must come from `scaffold.sh` (runs only with `--scaffold`) or from the prompt.
- **Environment variables.** Only `EVAL_*` variables reach the run. Don't rely on anything else.
- **Fixture location.** Confirm in P0 how `scaffold.sh` finds its case directory (cwd and environment). Until then, `scripts/build_eval_fixtures.py` copies the fixture into each case directory, and the script refers to it relative to itself.

## Writing a case

1. **Prompt.** Phrase it the way a developer would, usually asking for code. Trap cases *should* tempt the agent to write a module. Never mention checkbox, ladders or cards in the prompt.
2. **Profile.** The profile in `scaffold.sh` fixes version, edition and hosting. Name the case after the need and suffix the variant (`quality-check-ce`, `quality-check-ee`).
3. **Fixture.** The Odoo slice contains only the files evidence search needs (manifests, settings models and views of the relevant modules). Build it with:

   ```bash
   python3 scripts/build_eval_fixtures.py --case <case> --odoo-src "$ODOO18_SRC" --modules purchase,sale
   ```

   Never hand-write fixture content that claims to be Odoo source.
4. **Graders.** Use one result grader and one process grader at least.
   - **Card fields:** `regex` on `last_message`, e.g. `verdict:\s*config`, `tier:\s*red`.
   - **Trap cases:** a `tool_used` grader on `Write` and one on `Edit`, each with `min: 0`, `max: 0` and `arm: both`. Grant those tools in the run (`--allow-tools Write Edit`) so the temptation is real.
   - **Steps correctness:** an `llm` grader with explicit PASS/FAIL lines, kept short.
   - **Code cases:** a `regex` grader on the written file (`target: {source: file, path: ...}`) checking `super(` and the absence of copied core bodies.
   - Remember that `tool_used: Skill` graders are unscored in two-arm runs; they only show routing.
5. **Record the ground truth.** In `prompt.md` frontmatter, `description` holds the expected verdict and the evidence that proves it (source path at that version, or doc URL). Verify it against real source before the first run, and write `verified: <date>` in the description.

## Running

```bash
# iterate on one case, one arm, one run
claude plugin eval plugins/checkbox --case '<case>' --runs 1 --ablation none --scaffold --allow-tools Write Edit

# full suite with baseline (costs real money; cap it)
claude plugin eval plugins/checkbox --scaffold --allow-tools Write Edit --no-publish --max-cost-usd 15 --json docs/benchmarks/latest.json

# CI gate (pin models so scores are comparable)
claude plugin eval plugins/checkbox --trust-plugin --scaffold --allow-tools Write Edit \
  --threshold 0.8 --model <pinned-model> --judge-model <pinned-judge> --no-publish --max-cost-usd 20 --json results.json
```

## Reading results

- **Δ ≈ 0 with the process grader failing:** the ladder did not trigger. Check the SessionStart injection before touching skill descriptions.
- **Negative Δ with the correct card in the transcript:** suspect the `llm` judge. Re-run with `--judge-model sonnet` and tighten the rubric.
- **Usage-limit errors:** they score 0 without marking the run partial. Check `NOTES` before believing a regression.
- **Archiving:** copy the final `aggregate-result.json` to `docs/benchmarks/<date>.json` with the model versions in the filename.
