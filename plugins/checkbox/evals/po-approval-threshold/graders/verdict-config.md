---
type: regex
target: trace
pattern: "verdict:\\s*config"
flags: i
---

The decision card's `verdict` field must be `config` -- confirmed against
real 18.0 source (`purchase/models/res_config_settings.py`
`po_order_approval` + `po_double_validation_amount`,
docs/ARCHITECTURE.md §11.3). `target: trace` because the card is written to
a file via the `Write` tool, not necessarily restated in the last message.
