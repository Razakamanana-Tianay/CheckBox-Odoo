---
name: mode
description: Switch checkbox's policy level (off, lite, full, strict) for this project. User-invoked only via /checkbox:mode <level>.
disable-model-invocation: true
---

Run this when the user types `/checkbox:mode <level>` or asks to change
how strict checkbox is.

Valid levels: `off`, `lite`, `full`, `strict`. `full` is the default.

- `off` -- no ladder injection, no guard.
- `lite` -- the compact ladder only, at session start; no per-turn reminder
  or subagent injection.
- `full` -- the complete ladder, a compact per-turn reminder, and subagent
  injection. Edits under a `custom_addons` root with no approved card get a
  reminder in context (`PreToolUse` `hookSpecificOutput.additionalContext`),
  but the edit is allowed. `PostToolUse` still classifies the file's risk
  tier and injects it. `Stop` still blocks once if addon files were touched
  with no card covering them (`hooks/stop.py`).
- `strict` -- the ladder text itself reads the same as `full` (it never
  claimed enforcement details in the first place), but `hooks/pre_edit.py`
  and `hooks/pre_bash.py` now actually **deny** the edit
  (`permissionDecision: deny`) when no approved card covers the addon,
  instead of just reminding. Tell the user this is real now -- it wasn't
  before P4 landed.

## Steps

1. Run `checkbox mode set <level>`. It writes the override to
   `.checkbox/local.json`, which takes priority over the profile's own
   `mode` field for this project going forward
   (`docs/ARCHITECTURE.md` §8.5's resolution order:
   `CHECKBOX_MODE` env > `.checkbox/local.json` > `profile.json:mode` >
   `"full"`). To change it for one session only instead of persistently,
   tell the user to set `CHECKBOX_MODE` in the shell that launches Claude
   Code rather than running this command.
2. Confirm the new level back to the user in one line. Run
   `checkbox mode show` if there's any doubt which source (env, local
   override, or profile default) is currently winning.
