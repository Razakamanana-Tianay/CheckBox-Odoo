"""PreToolUse guard on Bash. `checkbox hook pre-bash`.

§8.2 row: PreToolUse, matcher Bash. Items 1-2 apply at every level (a
human-only act stays human-only when the mode is lowered), 3 in full and
strict, 4 in strict. Denies:

1. any command running `checkbox approve` -- approval is a human act done
   in the human's own terminal (§5.2), never through the agent's shell;
2. commands that write to or move `.checkbox/approvals.json` (write verbs
   only -- reading the approved state is fine);
3. SQL `UPDATE`/`DELETE`/`INSERT`/`TRUNCATE`/`DROP`/`ALTER` on ledger tables
   (schema-qualified or quoted names included; a heuristic, per §8.2;
   its limits are documented in the deny reason);
4. in strict only, `checkbox mode set`, `checkbox profile write` and shell
   writes to `.checkbox/local.json`/`profile.json` -- what could switch the
   guard off.

The heuristic denies only obvious write verbs against approvals.json, so
`cat .checkbox/approvals.json` passes while `rm`/`mv`/redirection of it is
blocked. SQL detection is substring-based on a fixed table list; it can't
see a table name built at runtime, and that residual gap is stated in the
reason (lib/checkbox/CLAUDE.md "document its limits in the reason text").
"""

from __future__ import annotations

import re
from typing import Any

from checkbox import mode as mode_mod
from checkbox.hooks.common import emit_deny, project_root, safe_main

_APPROVE_RE = re.compile(r"\bcheckbox\s+approve\b")


def _writes_re(names: str) -> re.Pattern[str]:
    """Shapes that write, move or replace a file called *names* (a regex).
    Each is anchored to the file (a redirect *into* it, a write verb in the
    same simple command), so a read piped elsewhere --
    `cat approvals.json | jq ... > out` -- passes."""
    return re.compile(
        "|".join(
            (
                rf">>?\s*['\"]?[^\s|;&<>]*{names}",
                rf"\b(mv|cp|rm|tee|touch|truncate|dd|install|ln|sed\s+-i\S*)\b[^|;&]*{names}",
                rf"\bgit\s+(checkout|restore|reset|rm|mv|apply)\b[^|;&]*{names}",
                rf"\b(python3?|py|perl|ruby|node)\s+-[ce]\b.*{names}",
            )
        )
    )


_APPROVALS_WRITE_RE = _writes_re(r"approvals\.json")
# Strict only: the commands and files that decide whether the guard applies
# (pre_edit.py protects the same two files from Write/Edit).
_WEAKEN_RE = re.compile(r"\bcheckbox\s+(mode\s+set|profile\s+write)\b")
_POLICY_WRITE_RE = _writes_re(r"(?:local|profile)\.json")
# Table = model name with dots as underscores (no `_table` override on any of
# these). Models checked in addons/account, addons/stock and
# odoo/addons/base/models/ir_sequence.py on the 17.0 and 18.0 branches.
_LEDGER_TABLES = (
    "account_move",
    "account_move_line",
    "account_bank_statement",
    "account_bank_statement_line",
    "account_journal",
    "account_partial_reconcile",
    "account_full_reconcile",
    "account_payment",
    "account_tax",
    "ir_sequence",
    "stock_move",
    "stock_move_line",
    "stock_quant",
    "stock_valuation_layer",
)
_SQL_RE = re.compile(
    r"\b(?:UPDATE|DELETE\s+FROM|INSERT\s+INTO|TRUNCATE(?:\s+TABLE)?|DROP\s+TABLE|ALTER\s+TABLE)"
    r"(?:\s+IF\s+EXISTS)?(?:\s+ONLY)?\s+"
    r'(?:"?\w+"?\.)?"?(?P<table>' + "|".join(_LEDGER_TABLES) + r')"?(?!\w)',
    re.IGNORECASE,
)


def _should_deny(command: str, mode: str = "full") -> tuple[bool, str]:
    # Human-only acts are denied at every level, `off` and `lite` included:
    # otherwise lowering the mode would be the first step of a self-approval.
    if _APPROVE_RE.search(command):
        return True, (
            "checkbox approve is human-only: run it in your own terminal, never "
            "through the agent's shell (§5.2)"
        )
    if _APPROVALS_WRITE_RE.search(command):
        return True, (
            "writing to .checkbox/approvals.json is human-only; this is a write-verb "
            "heuristic, so a cleverer writer could slip through"
        )
    if mode == "strict" and (
        _WEAKEN_RE.search(command) or (".checkbox" in command and _POLICY_WRITE_RE.search(command))
    ):
        return True, (
            "strict mode: the policy level and the profile are changed only by a human, "
            "in their own terminal (`checkbox mode set <level>` / `checkbox profile write`)"
        )
    match = _SQL_RE.search(command) if mode in ("full", "strict") else None
    if match:
        table = match.group("table")
        return True, (
            f"direct SQL on ledger table {table!r} is a red-tier change (§6.1); "
            "this is a substring heuristic that misses dynamically-built table names"
        )
    return False, ""


def _run(payload: dict[str, Any]) -> None:
    command = (payload.get("tool_input") or {}).get("command") or ""
    # Human-only checks first, before anything that reads project files: a
    # corrupt profile.json must not be a way around them.
    deny, reason = _should_deny(command, "off")
    if not deny:
        deny, reason = _should_deny(command, mode_mod.resolve(project_root(payload)))
    if deny:
        emit_deny("PreToolUse", reason)


def main() -> int:
    return safe_main(_run)


if __name__ == "__main__":
    raise SystemExit(main())
