"""Budget checks from the repo's CLAUDE.md non-negotiable #5.

The 10,000-char hook output cap is deliberately included even though its
existence could only be confirmed as TODO(verify) -- keeping it costs
nothing (every other budget here sits well under it) and protects against
silent truncation if the cap turns out to be real. That asymmetry is
intentional, not an oversight.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugins" / "checkbox" / "lib"))

from checkbox import ladder  # noqa: E402
from checkbox.profile import Profile  # noqa: E402

HOOK_OUTPUT_CAP = 10_000
SESSION_START_CAP = 6_000
PER_PROMPT_CAP = 400

_REALISTIC_PROFILES = [
    Profile(odoo_version="18.0", edition="community", hosting="on-premise", mode="full"),
    Profile(odoo_version="17.0", edition="enterprise", hosting="odoo-sh", mode="strict"),
    Profile(odoo_version="18.0", edition="community", hosting="online", mode="lite"),
    Profile(),  # undetected profile -- placeholders fall back to their longest text
]


def test_compact_ladder_fits_per_prompt_budget():
    for profile in _REALISTIC_PROFILES:
        rendered = ladder.render("lite", profile)
        assert len(rendered) <= PER_PROMPT_CAP, (
            f"lite render is {len(rendered)} chars for {profile.odoo_version}/"
            f"{profile.edition}/{profile.hosting}, budget is {PER_PROMPT_CAP}"
        )


def test_full_ladder_fits_session_start_budget():
    for profile in _REALISTIC_PROFILES:
        rendered = ladder.render(profile.mode if profile.mode != "off" else "full", profile)
        assert len(rendered) <= SESSION_START_CAP
        assert len(rendered) <= HOOK_OUTPUT_CAP
