---
type: llm
focus: trace
---

PASS if the response identifies the extension point as overriding a
stock.picking validation method (e.g. `button_validate` or `_action_done`)
and explicitly calls `super()` -- extension point #5 in
docs/ARCHITECTURE.md §4.3 ("overriding a core action or business method").

FAIL if no extension point is named, if it proposes a different model
(e.g. sale.order, account.move), if it doesn't mention `super()`, or if it
copies a core method body instead of calling super() (§4.3's "never
allowed" list).
