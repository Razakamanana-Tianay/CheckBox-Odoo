---
type: llm
focus: trace
---

PASS if the response's extension point is view inheritance (xpath on the
quotation form, docs/ARCHITECTURE.md §4.3 #1) plus a new field (§4.3 #2),
and if it proposes overriding or copying a core method to achieve this,
that counts as FAIL.

FAIL if it proposes overriding a business method (e.g. sale.order's
action_confirm), copying a core method body, or modifying a model outside
sale.order/its report templates.
