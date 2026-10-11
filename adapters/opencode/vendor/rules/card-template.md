# Decision card template

Source: docs/ARCHITECTURE.md §5.1. Copy this block into
`.checkbox/decisions/NNNN-slug.md` (get `NNNN` from `checkbox card next-id`),
fill every field, then run `checkbox card validate <file>` before telling
the user the card is ready for `checkbox approve`.

````markdown
# NNNN — short title

```checkbox-card
id: NNNN
need: one sentence, who does what, when, with which data
profile: {version} / {edition} / {hosting}
verdict: skip | standard | config | nocode | module | code
evidence: kind | ref ; kind | ref   (kind: source, docs, oca, live, unverified)
steps: click path, or the extension point + super() note for code
addons: comma-separated module names this card authorizes changes in, or -
extension_point: one of rules/extension-points.md's five, or -
tier: - | green | amber | red   (required for verdict: code or module)
upgrade_cost: none | low | medium | high, with a one-line reason
status: proposed
```

Context, rejected options, open questions (free text).
````

Field notes:

- `verdict: standard | config | module` needs at least one `evidence` item
  that isn't `unverified` -- `checkbox card validate` rejects the card
  otherwise. On Online, `docs`-only evidence is sufficient (there's no
  source to read).
- `verdict: module` with `oca` evidence: write the ref as `checkbox search`
  prints it in `card_ref` (`OCA/<repo>/<module> branch=<ver> license=<L>
  last_commit=<date>`); validate rejects a missing field or a branch other
  than the project's.
- `addons` lists module directory names (`my_module`), the ones that sit
  under a `custom_addons` root from `.checkbox/profile.json` -- never the
  root itself or a path. `verdict: code` needs at least one; in strict mode
  only the modules listed on an approved card can be edited.
- Never write client data into a card. `checkbox card validate` lints for
  emails, IBANs and VAT-like tokens as a courtesy check, not a guarantee.
- `status` stays `proposed`. Only a human runs `checkbox approve NNNN` in
  their own terminal; the agent is never the one that approves.
