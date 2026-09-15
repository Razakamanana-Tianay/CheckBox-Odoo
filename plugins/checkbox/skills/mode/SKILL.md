---
name: mode
description: Switch checkbox's policy level (off, lite, full, strict) for this project. User-invoked only via /checkbox:mode <level>.
disable-model-invocation: true
---

Run this when the user types `/checkbox:mode <level>` or asks to change
how strict checkbox is.

Valid levels: `off`, `lite`, `full`, `strict`. `full` is the default.

- `off` -- no ladder injection, no guard (guard ships in P4).
- `lite` -- the compact ladder only, at session start; no per-turn reminder
  or subagent injection.
- `full` -- the complete ladder at session start, a compact per-turn
  reminder, and injection into subagents. No hard enforcement.
- `strict` -- same content as `full` for now. The difference (denying an
  edit that has no approved card) is a P4 feature; don't tell the user
  edits are being blocked until that guard actually exists --
  `docs/notes/platform-facts.md` §1.8 and `rules/ladder.md`'s render logic
  are explicit that `strict` doesn't yet change behaviour beyond `full`.

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
