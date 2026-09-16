"""Shared hook plumbing: stdin reading, the fail-open wrapper, output emitters.

Every fact this module encodes about hook I/O was verified against the
official hooks reference (code.claude.com/docs/en/hooks) -- change the
shape here only after re-verifying there, per
plugins/checkbox/CLAUDE.md's "Before changing any output shape" rule.
"""

from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Callable
from typing import Any


def read_stdin_json() -> dict[str, Any]:
    """Read and parse the hook's stdin JSON payload. Empty or invalid -> {}.

    A hook must never crash on malformed input (non-negotiable #4), so this
    fails to an empty dict rather than raising.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def emit_context(text: str) -> None:
    """SessionStart / UserPromptSubmit: plain stdout is added as context
    directly, no JSON wrapper (verified against code.claude.com/docs/en/hooks,
    and corroborated by Ponytail's shipped ponytail-runtime.js:
    `process.stdout.write(context)` for these two events specifically)."""
    if text:
        sys.stdout.write(text)


def emit_hook_context(event: str, text: str) -> None:
    """Generic hookSpecificOutput context injection for events whose plain
    stdout is *not* added to the transcript (SubagentStart, PreToolUse,
    PostToolUse -- verified against the hooks reference: these events are
    not among the plain-stdout ones)."""
    if not text:
        return
    payload = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
    sys.stdout.write(json.dumps(payload))


def emit_deny(event: str, reason: str) -> None:
    """PreToolUse deny: permissionDecision in hookSpecificOutput, exit 0 --
    never exit 2 for this (non-negotiable #7: exit 2 blocks unconditionally
    and bypasses the reason; the JSON form is what carries the explanation
    the agent needs to see)."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))


def safe_main(func: Callable[[dict[str, Any]], int | None]) -> int:
    """Wrap a hook entry point per non-negotiable #4: a crash logs to stderr,
    prints nothing to stdout, and exits 0. This is the only place in the
    codebase allowed to swallow an exception -- the CLI (a human at a
    terminal) must never have errors hidden from it the way a hook must.

    *func* may return an int (e.g. 2, for a Stop hook that needs to block)
    to propagate as the process exit code; returning None means 0.
    """
    try:
        payload = read_stdin_json()
        result = func(payload)
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return 0
    return int(result) if result is not None else 0
