---
type: regex
target: trace
pattern: "verdict:\\s*code"
flags: i
match: not_contains
---

Only the negative is graded here -- see case.yaml for why the positive
claim (exact blocking mechanism) is TODO(verify) and ungraded. The Quality
app is real and Enterprise-only, so `code` would mean the agent missed
that entirely.
