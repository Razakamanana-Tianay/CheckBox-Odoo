"""PreToolUse guard on Bash. `checkbox hook pre-bash`.

§8.2 row: PreToolUse, matcher Bash. Levels: full, strict. Denies:

1. any command running `checkbox approve` -- approval is a human act done
   in the human's own terminal (§5.2), never through the agent's shell;
2. commands that write to or move `.checkbox/approvals.json` (write verbs
   only -- reading the approved state is fine);
3. SQL `UPDATE`/`DELETE`/`INSERT` on ledger tables (a heuristic, per §8.2;
   its limits are documented in the deny reason).

The heuristic denies only obvious write verbs against approvals.json, so
`cat .checkbox/approvals.json` passes while `rm`/`mv`/redirection of it is
blocked. SQL detection is substring-based on a fixed table list; it can't
see a table name built at runtime, and that residual gap is stated in the
reason (lib/checkbox/CLAUDE.md "document its limits in the reason text").
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from checkbox import mode as mode_mod
from checkbox.hooks.common import emit_deny, safe_main

_APPROVE_RE = re.compile(r"\bcheckbox\s+approve\b")
_APPROVALS_WRITE_VERBS = (
    ">",
    ">>",
    "mv ",
    "cp ",
    "rm ",
    "tee ",
    "touch ",
    "truncate",
    "sed -i",
    "dd ",
)
_LEDGER_TABLES = (
    "account_move",
    "account_move_line",
    "account_bank_statement",
    "account_bank_statement_line",
    "account_journal",
    "account_partial_reconcile",
    "stock_move",
    "stock_move_line",
    "stock_quant",
    "stock_valuation_layer",
)
_SQL_RE = re.compile(
    r"\b(UPDATE|DELETE\s+FROM|INSERT\s+INTO)\s+(" + "|".join(_LEDGER_TABLES) + r")\b",
    re.IGNORECASE,
)


def _should_deny(command: str) -> tuple[bool, str]:
    if _APPROVE_RE.search(command):
        return True, (
            "checkbox approve is human-only: run it in your own terminal, never "
            "through the agent's shell (§5.2)"
        )
    if ".checkbox/approvals.json" in command and any(
        verb in command for verb in _APPROVALS_WRITE_VERBS
    ):
        return True, (
            "writing to .checkbox/approvals.json is human-only; this is a write-verb "
            "heuristic, so a cleverer writer could slip through"
        )
    match = _SQL_RE.search(command)
    if match:
        table = match.group(2)
        return True, (
            f"direct SQL on ledger table {table!r} is a red-tier change (§6.1); "
            "this is a substring heuristic that misses dynamically-built table names"
        )
    return False, ""


def _run(payload: dict[str, Any]) -> None:
    root = Path(payload.get("cwd") or ".").resolve()
    resolved_mode = mode_mod.resolve(root)
    if resolved_mode not in ("full", "strict"):
        return
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") or ""
    deny, reason = _should_deny(command)
    if deny:
        emit_deny("PreToolUse", reason)


def main() -> int:
    return safe_main(_run)


if __name__ == "__main__":
    raise SystemExit(main())
