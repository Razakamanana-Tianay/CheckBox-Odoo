---
name: ladder
description: Walk the Odoo fit-gap ladder before writing any code for this project's Odoo/OCA addons -- standard, then configuration, then no-code, then an existing module, then code. Use for requests to add a module, custom field, override, automation, or any change touching Odoo models, views or business logic.
---

This project uses a fit-gap policy for Odoo changes (see `.checkbox/profile.json`
and the SessionStart context for the current profile and policy level). Before
writing or editing any Odoo addon code, run the ladder in `${CLAUDE_PLUGIN_ROOT}/rules/ladder.md`
(or `checkbox ladder render --level full` to print it fresh against the current
profile) -- don't restate it here, that file is the single source of truth.

## How to use this skill

1. **Understand first.** Restate the business need in one sentence. If the
   ask is ambiguous, ask at most one clarifying question -- don't default to
   asking when a reasonable reading exists.
2. **Read before judging.** If the change would touch an existing model or
   custom addon, read that code before picking a rung. The ladder shortens
   the solution, never the reading.
3. **Climb the ladder**, stopping at the first rung that holds. For rung 2
   (standard) and rung 5 (module), evidence must come from `checkbox search`
   or delegating to the `standard-scout` agent -- never from model memory.
   As of this plugin's current version, the index only covers `source`
   evidence (addon manifests and `res.config.settings` fields/views) --
   `docs`/`oca` evidence isn't indexed yet. If a search finds nothing,
   evidence is `unverified` and the card must say so; don't guess.
4. **Hosting and edition change what's available.** Read
   `${CLAUDE_PLUGIN_ROOT}/rules/hosting.md` when the profile's hosting is
   `online` or `odoo-sh`, or the answer might assume a capability (custom
   Python modules, Studio) the project doesn't have.
5. **Rung 6 (code) needs an extension point.** Read
   `${CLAUDE_PLUGIN_ROOT}/rules/extension-points.md` and name the least
   invasive one that covers the gap -- not the first one you think of.
6. **Record the answer as a card.** Use the `card` skill to draft
   `.checkbox/decisions/NNNN-slug.md` from
   `${CLAUDE_PLUGIN_ROOT}/rules/card-template.md`. Don't write addon code
   before the card exists with `status: proposed`.

## What this skill does not do

It doesn't approve cards (`checkbox approve` is a human-only CLI command),
and it doesn't decide the business need is legitimate -- it only forces the
question to be asked and the standard alternative to be put on the table
before code exists.
