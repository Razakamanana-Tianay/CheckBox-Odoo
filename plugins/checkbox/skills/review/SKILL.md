---
name: review
description: Produce a checkbox blast-radius review of a git diff (or changes since approval) -- classify each changed file, send red-tier items to the ledger-reviewer agent, and attach its report to the card. Use after "review this diff", before/within the card step for a red change, or when the user asks whether the change is safe.
---

A tier report is deterministic output of `checkbox classify` -- never a
model-memory guess. Classification rules live in
`${CLAUDE_PLUGIN_ROOT}/rules/risk/` and are verified against real Odoo
source with `checkbox rules verify`.

## Steps

1. **Get the diff.** Run `git diff` (or `git diff <base>..HEAD` if the card's
   already approved against some base) from `.checkbox/`'s project root.
2. **Classify every changed file** with `checkbox classify <file> --root .
   --json`. Collect `{file -> {tier, reasons}}`.
3. **Report the tiers** to the user in a short table. A 🔴 red item means
   a human reads every line of it; 🟠 amber is reviewed before merge; 🟢
   needs no further gate (§6.1).
4. **Run the `ledger-reviewer` agent on the red items** (delegate a small
   prompt listing the red files/diffs and the checks you want run). Save the
   checklist it returns as `.checkbox/decisions/NNNN-ledger.md` (where NNNN
   is the card id), so `checkbox approve NNNN` finds the required red-card
   report (§5.2). Never summarize or shorten the report yourself -- the
   approval check only cares that the file exists, but the human reading the
   red lines depends on its full content.
5. **Report back** in one block: tier per file, the ledger-reviewer verdict,
   and the path of the saved report. Don't stop on 🔴 -- review is a gate
   check, not a refusal.