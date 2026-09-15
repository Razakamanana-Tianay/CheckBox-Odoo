---
name: help
description: Show checkbox's command reference. User-invoked only via /checkbox:help.
disable-model-invocation: true
---

Run this when the user types `/checkbox:help` or asks what checkbox can do.
Print the following (or a lightly reworded version of it -- keep it this
short, don't add marketing):

```
checkbox -- a fit-gap gate for Odoo coding agents

/checkbox:init            detect and confirm this project's profile
/checkbox:mode <level>    off | lite | full | strict (default: full)
/checkbox:help            this message

Automatic (no command needed):
  Before Odoo code changes, the ladder skill walks standard -> configure ->
  no-code -> existing module -> code, and the card skill records the
  verdict at .checkbox/decisions/NNNN-slug.md.

Human-only, from your own terminal (never run by the agent):
  checkbox approve NNNN     approve a proposed card

CLI (works without Claude Code too):
  checkbox doctor
  checkbox profile detect|show|write
  checkbox ladder render --level lite|full|strict
  checkbox card next-id|validate <file>
  checkbox mode show|set <level>

Current status: the source/docs/OCA evidence index (checkbox search),
the risk classifier and the PreToolUse/PostToolUse/Stop guard are not
implemented yet (tracked as P3/P4 in docs/ARCHITECTURE.md) -- say so if
asked, don't imply they already run.
```
