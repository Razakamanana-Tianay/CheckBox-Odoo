"""Per-session state: `.checkbox/.session/<session_id>.json`.

Tracks what a hook needs across events in one Claude Code session without a
platform-provided mechanism for it: there is no documented Stop-hook
loop-protection flag, so the Stop hook's single-block behaviour is built on
this file instead. Gitignored -- session state is never committed (see repo
.gitignore).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _default() -> dict[str, Any]:
    # Fresh lists/dicts every call: `load()` hands callers a copy of the
    # defaults, so the nested lists must not be shared module globals, or a
    # `record_touched_addon(...).append(...)` would leak across sessions --
    # a single module-level default dict, shallow-copied per call, would
    # leave every copy pointing at the same nested list object.
    return {"touched_addons": [], "cards_seen": [], "stop_block_count": 0}


def _session_path(root: Path, session_id: str) -> Path:
    return Path(root) / ".checkbox" / ".session" / f"{session_id}.json"


def load(root: Path, session_id: str) -> dict[str, Any]:
    path = _session_path(root, session_id)
    if not path.is_file():
        return _default()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default()
    merged = _default()
    merged.update({k: v for k, v in data.items() if k in merged})
    return merged


def save(root: Path, session_id: str, state: dict[str, Any]) -> Path:
    path = _session_path(root, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return path


def record_touched_addon(root: Path, session_id: str, addon: str) -> dict[str, Any]:
    state = load(root, session_id)
    if addon not in state["touched_addons"]:
        state["touched_addons"].append(addon)
    save(root, session_id, state)
    return state


def increment_stop_block_count(root: Path, session_id: str) -> int:
    state = load(root, session_id)
    state["stop_block_count"] = int(state.get("stop_block_count", 0)) + 1
    save(root, session_id, state)
    return state["stop_block_count"]
