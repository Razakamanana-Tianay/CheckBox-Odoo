"""Human approval of decision cards: `.checkbox/approvals.json`.

docs/ARCHITECTURE.md §5.2: approval is a human act. `checkbox approve NNNN`
runs in the human's own terminal (a code agent can't reach it -- the
`pre-bash` guard denies any command that invokes `checkbox approve`), and
writes the card id, a hash of the card block, the git user and a timestamp.
Editing an approved card invalidates its approval because the hash changes.

`approvals.json` is committed with the code (Appendix B: "approvals.json:
committed"), so the approval trail survives clones. The file is keyed by
card id; an entry only proves the *card block it was computed on* was
approved, which is why every check re-reads the live card file and compares
hashes rather than trusting a stale entry.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from checkbox import card as card_mod
from checkbox import profile as profile_mod

_FENCE_RE = card_mod._FENCE_RE  # noqa: SLF001 -- same fence the parser uses
_LEDGER_SUFFIX = "-ledger.md"


def _approvals_path(root: Path) -> Path:
    return Path(root) / ".checkbox" / "approvals.json"


def read(root: Path) -> dict[str, dict[str, Any]]:
    """Load `.checkbox/approvals.json`; a missing or corrupt file is empty."""
    path = _approvals_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and k == v.get("card_id")}


def card_hash(raw_text: str) -> str:
    """sha256 of the exact fenced card block. Any edit to the block --
    even re-flowing a line -- changes the hash and voids the approval."""
    match = _FENCE_RE.search(raw_text)
    block = match.group(0) if match else raw_text
    return hashlib.sha256(block.encode("utf-8")).hexdigest()


def _card_file(root: Path, card_id: str) -> Path | None:
    matches = sorted(
        p
        for p in (Path(root) / ".checkbox" / "decisions").glob(f"{card_id}-*.md")
        if not p.name.endswith(_LEDGER_SUFFIX)
    )
    return matches[0] if matches else None


def _git_user() -> str:
    try:
        out = subprocess.run(
            ["git", "config", "--get", "user.name"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        name = out.stdout.strip()
        return name or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _write_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with open(tmp_name, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os_replace(tmp_name, path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def os_replace(src: str, dst: Path) -> None:
    """Swap *src* over *dst*. Split out so tests can monkeypatch the rename
    and so the import stays stdlib-only (os.replace is imported lazily to
    keep this module's failed-hook path free of any syscalls on import)."""
    import os

    os.replace(src, dst)


def approve(
    root: Path,
    card_id: str,
    *,
    approver: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Approve card *card_id* in *root*'s `.checkbox/decisions/`.

    Returns the new approval record. Raises ValueError with a human-readable
    reason when the card can't be approved: missing file, invalid card,
    status isn't `proposed`, a red card with unverified evidence, or a red
    card with no sibling `NNNN-ledger.md` report (§5.2).
    """
    root = Path(root)
    card_file = _card_file(root, card_id)
    if card_file is None:
        raise ValueError(f"no card {card_id!r} found in .checkbox/decisions/")
    raw_text = card_file.read_text(encoding="utf-8")
    card = card_mod.parse(raw_text)
    profile = None
    try:
        profile = profile_mod.load(root)
    except FileNotFoundError:
        pass
    errors = card_mod.validate(card, profile=profile, raw_text=raw_text)
    if errors:
        raise ValueError(f"{card_file.name} is not a valid card: {'; '.join(errors)}")
    if card.get("status") != "proposed":
        raise ValueError(f"card {card_id} status is {card.get('status')!r}, not 'proposed'")

    ledger_report: str | None = None
    if card.get("tier") == "red":
        for item in card.get("evidence", []):
            if item.get("kind") == "unverified":
                raise ValueError(
                    f"card {card_id} is red and carries unverified evidence; a red card "
                    "cannot be approved until every evidence item is confirmed (§5.2)"
                )
        report = Path(root) / ".checkbox" / "decisions" / f"{card_id}{_LEDGER_SUFFIX}"
        if not report.is_file():
            raise ValueError(
                f"card {card_id} is red and has no {_LEDGER_SUFFIX} ledger-reviewer report "
                "attached; run the review skill to produce one before approving (§5.2)"
            )
        ledger_report = report.name

    record = {
        "card_id": card_id,
        "hash": card_hash(raw_text),
        "approver": approver or _git_user(),
        "approved_at": now or datetime.now(timezone.utc).isoformat(),
    }
    if ledger_report:
        record["ledger_report"] = ledger_report

    approvals = read(root)
    approvals[card_id] = record
    _write_atomic(_approvals_path(root), approvals)
    return record


def is_approved(root: Path, card_id: str, raw_text: str) -> bool:
    """True when *raw_text*'s card block hash matches card *card_id*'s
    approval entry. A stale entry (the card was edited after approval) is
    deliberately *not* approved."""
    entry = read(root).get(card_id)
    return bool(entry) and entry.get("hash") == card_hash(raw_text)


def covers_addon(root: Path, addon: str) -> list[str]:
    """Ids of approved cards whose `addons` list includes *addon*.

    Re-reads the live card files (approvals.json alone holds no addon
    names), so a card edited after approval drops out automatically.
    """
    root = Path(root)
    covers: list[str] = []
    for entry in read(root).values():
        card_id = entry["card_id"]
        card_file = _card_file(root, card_id)
        if card_file is None:
            continue
        try:
            raw_text = card_file.read_text(encoding="utf-8")
            card = card_mod.parse(raw_text)
        except (ValueError, OSError):
            continue
        if addon in card.get("addons", []):
            if is_approved(root, card_id, raw_text):
                covers.append(card_id)
    return sorted(covers)
