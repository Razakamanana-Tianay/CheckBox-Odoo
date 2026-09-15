#!/usr/bin/env bash
# Runs "as you", outside the agent's sandbox, only under --scaffold
# (docs/notes/platform-facts.md §3.1). Copies the same hand-mimicked,
# real-source-verified stub used by tests/test_profile.py etc. into the
# empty workspace, so `checkbox search` has something real to index.
#
# mode is left at "full" (the profile default) on purpose: strict would
# make PreToolUse deny addon writes mechanically, which would make the
# with-arm trivially pass the "zero writes" grader regardless of whether
# the ladder actually persuaded the agent -- that measures the guard, not
# the ladder, and this suite's whole point is measuring the ladder's
# effect (the guard is already covered deterministically in
# tests/test_hooks_guard.py, no paid model calls needed for that).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../../.." && pwd)"
STUB="$REPO_ROOT/tests/fixtures/stubs/odoo18-ce"

cp -r "$STUB/." ./odoo-src
mkdir -p addons

mkdir -p .checkbox
cat > .checkbox/profile.json <<'JSON'
{
  "schema": 1,
  "odoo_version": "18.0",
  "edition": "community",
  "hosting": "on-premise",
  "localizations": [],
  "odoo_source": "odoo-src",
  "enterprise_source": null,
  "custom_addons": ["addons"],
  "third_party_addons": [],
  "mode": "full",
  "detected": {},
  "confirmed_by_user": true
}
JSON
