"""Mode resolution: CHECKBOX_MODE env > .checkbox/local.json > profile.json:mode > "full".

docs/ARCHITECTURE.md §8.5.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from checkbox.profile import VALID_MODES
from checkbox.profile import load as load_profile

DEFAULT_MODE = "full"


def resolve(root: Path) -> str:
    env_mode = os.environ.get("CHECKBOX_MODE")
    if env_mode in VALID_MODES:
        return env_mode

    local_path = Path(root) / ".checkbox" / "local.json"
    if local_path.is_file():
        try:
            local = json.loads(local_path.read_text(encoding="utf-8"))
            local_mode = local.get("mode")
            if local_mode in VALID_MODES:
                return local_mode
        except (json.JSONDecodeError, OSError):
            pass  # fall through to profile/default -- a broken local.json must never crash a hook

    try:
        profile = load_profile(root)
    except FileNotFoundError:
        return DEFAULT_MODE
    if profile.mode in VALID_MODES:
        return profile.mode
    return DEFAULT_MODE


def write_local_mode(root: Path, mode: str) -> Path:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    path = Path(root) / ".checkbox" / "local.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, str] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data["mode"] = mode
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path
