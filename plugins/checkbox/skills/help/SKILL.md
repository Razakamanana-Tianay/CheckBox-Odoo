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
  checkbox approve NNNN     approve a proposed card (red cards need a
                            ledger-reviewer report attached first)

CLI (works without Claude Code too):
  checkbox doctor
  checkbox profile detect|show|write
  checkbox ladder render --level lite|full|strict
  checkbox card next-id|validate <file>
  checkbox mode show|set <level>
  checkbox search "<query>" [--kind source] [--profile <file>]
  checkbox classify <file> [--version|--profile|--root]
  checkbox rules verify --version <v> --odoo-src <path>

Automatic guard (strict mode only):
  Editing a custom addon with no approved card is denied (PreToolUse);
  in full mode the same situation only gets a reminder, not a denial.
  Every edit is classified green/amber/red afterward (PostToolUse), and
  stopping is blocked once if addon files were touched with no card
  covering them (Stop).

Current status: `checkbox search` covers `source` evidence only (addon
manifests, res.config.settings fields/views) -- `docs` and `oca` evidence
aren't indexed yet (tracked as a P3 follow-up in docs/ARCHITECTURE.md).
Say so if asked, don't imply they already run.
```
