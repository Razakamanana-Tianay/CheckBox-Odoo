# Hosting and edition constraints

Source: docs/ARCHITECTURE.md §4.2. Loaded on demand by the `ladder` skill
when the rung-4/rung-6 answer depends on hosting.

| Hosting | Custom Python modules | Studio | Source available for evidence |
|---|---|---|---|
| Odoo Online | No | Yes | No: evidence is docs-only |
| Odoo.sh | Yes | Yes | Yes (Enterprise + custom) |
| On-premise, Community | Yes | No | Yes |
| On-premise, Enterprise | Yes | Yes | Yes |

- **Online**: the ladder ends at rung 4. If a gap remains, the card says so
  and lists "move to Odoo.sh" as a cost, not a default.
- **Edition**: the truth is the presence of a module in the configured
  addons paths (`web_enterprise`, see `checkbox profile detect`), never
  model memory.
- Re-check this table at each major Odoo release; it's data (`hosting.json`
  will carry the machine-readable form once `init`/`search` needs it, P3+).
