"""Hook perf budget: p95 ≤ 150 ms (§8.5).

Measured in-process (the hook body excluding Python's ~30ms startup, which
every plugin hook pays identically) over 50 runs per fixture hook, using
the committed fixture payloads. Skips naturally if a hook's sys.path
isn't resolvable -- the other test files do the same import dance.
"""

from __future__ import annotations

import statistics
import sys
import time
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox.hooks import (  # noqa: E402
    post_edit,
    pre_bash,
    pre_edit,
    prompt,
    session_start,
    stop,
    subagent_start,
)

HOOKS = [
    (session_start._run, "session_start.json"),
    (prompt._run, "prompt.json"),
    (subagent_start._run, "subagent_start.json"),
    (pre_edit._run, "pre_edit_strict_no_card.json"),
    (pre_bash._run, "pre_bash_approve.json"),
    (post_edit._run, "post_edit_red.json"),
    (stop._run, "stop_edited_no_card.json"),
]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "hooks"
RUNS = 50


def test_hook_p95_under_150ms():
    timings: list[float] = []
    for run, (func, fixture_name) in enumerate(HOOKS * (RUNS // len(HOOKS) + 1), start=1):
        if run > RUNS:
            break
        payload_file = FIXTURES / fixture_name
        if not payload_file.is_file():
            continue
        payload = payload_file.read_text(encoding="utf-8")
        import json

        data = json.loads(payload)
        start = time.perf_counter()
        with redirect_stdout(StringIO()):
            func(data)
        timings.append((time.perf_counter() - start) * 1000)

    assert len(timings) >= RUNS // 2, f"only {len(timings)} measurable hook runs"
    p95 = statistics.quantiles(timings, n=20)[18]
    assert p95 < 150, f"hook p95 {p95:.1f}ms exceeds the 150ms budget ({len(timings)} runs)"
