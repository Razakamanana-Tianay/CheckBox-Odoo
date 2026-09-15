---
type: tool_used
tool: Write
input_match: "\"file_path\"\\s*:\\s*\"addons/"
min: 0
max: 0
---

Trap: `po_order_approval` already covers this on 18.0 CE. A ladder-walking
agent must not write any file under `addons/` (the profile's
`custom_addons` root) -- that would mean it skipped rung 2/3 and jumped to
writing code. Scored in both arms (default for a non-Skill tool_used
grader), since a positive Δ here is the whole point of the trap.
