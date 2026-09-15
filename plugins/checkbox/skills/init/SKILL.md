---
name: init
description: Detect and confirm this project's Odoo version, edition, hosting and addon paths, then save .checkbox/profile.json. User-invoked only via /checkbox:init.
disable-model-invocation: true
---

Run this when the user types `/checkbox:init`, or asks to set up checkbox
for this project.

## Steps

1. **Detect.** Run `checkbox profile detect --json` (pass a path if the
   Odoo checkout or project root isn't the current directory). This reads
   `odoo/release.py` and checks for `web_enterprise/__manifest__.py` -- it
   never guesses version or edition from anything else.
2. **Confirm one field at a time**, in this order: `odoo_version`,
   `edition`, `hosting`, `odoo_source`, `enterprise_source`,
   `custom_addons`, `third_party_addons`, `mode`. For each:
   - If `detect` found it, show the value and its `detected` reason, and
     ask the user to confirm or correct it.
   - If `detect` did not find it (most commonly `hosting`, and
     `custom_addons`/`third_party_addons` -- `detect` deliberately never
     guesses which addon roots hold custom code, see profile.py), ask for it
     directly. For `hosting` specifically: there is no reliable local
     signal for Odoo.sh, so always ask rather than guessing from environment
     variables.
   - Never silently accept a detected value without showing the user what
     it is and where it came from.
3. **Write.** Once every field is confirmed, pipe the completed profile as
   JSON to `checkbox profile write` (set `confirmed_by_user: true`). It
   re-validates before saving and reports errors if anything is
   inconsistent (e.g. `hosting: online` with an `odoo_source` set).
4. **Offer to build the source index, don't build it silently.** Ask
   before running `checkbox search` for the first time in this project --
   it builds and caches a local SQLite index from the addon paths just
   confirmed, which touches disk (harmless, but still worth asking first).
   The `docs` (odoo/documentation) and `oca` (curated OCA repos) indexes
   described in docs/ARCHITECTURE.md §7 additionally need network access
   and aren't implemented yet (tracked as P3 follow-up) -- say so plainly if
   asked, rather than claiming they already run.

## Output

End by pointing at `checkbox profile show` so the user can see the saved
file, and mention that the ladder skill will now use this profile
automatically on the next session start.
