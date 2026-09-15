# rules: ladder text and risk data

This directory is the product's knowledge. Treat every line as a claim a user will act on.

## Files

```
ladder.md           canonical full ladder (template; see ARCHITECTURE Appendix A)
ladder.compact.md   ≤ 400 chars; per-prompt and subagent reminder
extension-points.md least→most invasive extension points, with one example each
hosting.json        hosting × edition matrix (custom python, studio, source availability)
risk/common.json    version-independent rules (sudo, cr.execute, auth='public', ir.rule, …)
risk/17.0.json      version overlays: models, methods, source file per entry
risk/18.0.json
risk/19.0.json
```

## Ladder text rules

- **Placeholders** use `{name}` and are rendered by `lib/fitgate/ladder.py`: `{profile_line}`, `{mode}`, `{version}`, `{edition}`, `{studio_clause}`, `{hosting_clause}`. An unknown placeholder is a test failure.
- **Tone** is factual policy ("This project uses…", "Cards are created with status proposed"). No "you MUST", no "SYSTEM:", no role-play. Claude Code warns that command-like injected text can be treated as prompt injection.
- **Rendered size:** `full` ≤ 6,000 chars; `compact` ≤ 400 chars. `tests/test_budgets.py` enforces both.
- **After any edit:** run `python3 scripts/build_adapters.py && python3 scripts/check_rule_copies.py`.
- **No Ponytail text.** Keep the wording ours.

## Risk data rules

- **Entry shape:**

  ```json
  "account.move": {
    "tier": "red",
    "methods": { "_post": "red" },
    "source": "addons/account/models/account_move.py",
    "note": "posting"
  }
  ```

- **`source` is required.** It is the file where the model or method is defined in that version's Community (or Enterprise) tree.
- **Verification.** Every entry must pass:

  ```bash
  plugins/fitgate/bin/fitgate rules verify --version 18.0 --odoo-src "$ODOO18_SRC" [--enterprise-src "$ODOO18_EE_SRC"]
  ```

  `verify` parses the `source` file with `ast` and fails if the model (`_name`/`_inherit`) or any listed method is not defined there. Entries for Enterprise-only models carry `"edition": "enterprise"` and are verified only when `--enterprise-src` is given.
- **Overlays.** An overlay may add entries, change tiers, or remove an entry with `"removed": true` plus a `note` explaining the version change. Never copy an overlay forward without re-running `verify` on the new version.
- **Tier definitions:** ARCHITECTURE §6.1. When unsure between amber and red, choose red and write the reason in `note`.
- **Tests.** Each rule id needs one positive and one negative fixture in `tests/fixtures/diffs/`.

## hosting.json rules

- **Content:** one entry per `hosting` × `edition`, with the keys `custom_python`, `studio`, `source_available`, `notes` and `verified` (a doc URL plus date).
- **Maintenance:** re-verify at each major Odoo release. If a capability is uncertain for a version (for example, Python in server actions on Online), set the value to `"unknown"`. The ladder then renders a neutral clause instead of a promise.
