# Extension points, least to most invasive

Source: docs/ARCHITECTURE.md §4.3. Loaded on demand by the `ladder` skill
once a card's verdict reaches rung 6 (`code`) and needs to name a specific
extension point.

1. View inheritance (xpath), QWeb report inheritance, menus, actions.
2. New fields, in this order: related or non-stored computed, then stored.
3. A new model linked by `Many2one`, instead of widening a core model.
4. Overriding a hook method designed for extension (the `_prepare_*` /
   `_get_*` families), always calling `super()`.
5. Overriding a core action or business method (🔴 red by definition).

Never allowed:

- copying a core method body;
- monkeypatching;
- raw SQL writes on ledger tables;
- `sudo()` added only to bypass access rights.

A card's `extension_point` field names which of 1-5 the change uses. Rung 6
code is always the gap only, at the lowest-numbered point that actually
covers it -- don't reach for #4/#5 when #1/#2 would do.
