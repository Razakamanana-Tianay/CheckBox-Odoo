---
name: card
description: Draft or update a checkbox decision card for an Odoo change, once the ladder skill has produced a verdict. Use after "what's the verdict", "write the card", or as the last step of walking the ladder.
---

A decision card is a Markdown file at `.checkbox/decisions/NNNN-slug.md`
recording one ladder verdict with its evidence. Format and field rules are
in `${CLAUDE_PLUGIN_ROOT}/rules/card-template.md` -- copy that template,
don't retype it from memory.

## Steps

1. **Get the id.** Run `checkbox card next-id` (or `--json` for scripting).
2. **Gather evidence** for the verdict. Delegate to the `standard-scout`
   agent and use only what it returns -- stop at the first rung it proves,
   and mark evidence `unverified` if it finds nothing rather than
   guessing. `standard-scout` only has `source` evidence to work with so
   far (addon manifests and `res.config.settings` fields/views); `docs` and
   `oca` evidence aren't indexed yet, so a genuinely undocumented feature
   will correctly come back `unverified` rather than confirmed.
3. **Fill the template** from `rules/card-template.md`: `id`, `need`
   (one sentence), `profile` (`{version} / {edition} / {hosting}`),
   `verdict`, `evidence`, `steps`, `addons`, `extension_point`, `tier`,
   `upgrade_cost`, `status: proposed`. Add context/rejected options as free
   text after the fenced block.
4. **Validate before finishing.** Run
   `checkbox card validate .checkbox/decisions/NNNN-slug.md`. Fix every
   error it reports -- it checks evidence sufficiency, `tier` requirements,
   `addons` against the profile's `custom_addons`, and a best-effort PII
   lint. Don't tell the user the card is ready until this passes.
5. **Never approve it.** `status` stays `proposed`. Tell the user the card
   is ready and that they approve it themselves with `checkbox approve
   NNNN` in their own terminal -- you have no path to running that command
   or to writing `.checkbox/approvals.json` directly.

## When the verdict is `code`

Don't write the addon code in the same turn as the card unless the user
already asked for both. Present the card first; a 🔴 `tier: red` card
additionally needs a `ledger-reviewer` report (P4+) before it can be
approved at all.
