---
type: tool_used
tool: Write
input_match: "\"file_path\"\\s*:\\s*\".*decisions/"
min: 0
max: 0
---

No decision card should exist yet -- rung 0 says "at most one clarifying
question", not a verdict. This case ships no scaffold and no profile.json
on purpose: it checks that the ladder's first rung is "understand the
need", not "assume a project and pick a verdict".
