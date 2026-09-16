"""Hook entry points.

HOOK_MAIN lives here, not in cli.py, so bin/checkbox's fast path can
dispatch a hook by importing only this module plus the one hook needed --
cli.py's top-level imports (approvals, card, knowledge, risk...) are for
the human-facing subcommands and add avoidable import time to every hook.
"""

from __future__ import annotations

HOOK_MAIN = {
    "session-start": "checkbox.hooks.session_start",
    "prompt": "checkbox.hooks.prompt",
    "subagent-start": "checkbox.hooks.subagent_start",
    "pre-edit": "checkbox.hooks.pre_edit",
    "pre-bash": "checkbox.hooks.pre_bash",
    "post-edit": "checkbox.hooks.post_edit",
    "stop": "checkbox.hooks.stop",
}
