#!/usr/bin/env bash
# See po-approval-threshold/scaffold.sh for the mode: full rationale.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../../.." && pwd)"
STUB="$REPO_ROOT/tests/fixtures/stubs/odoo18-ee"

cp -r "$STUB/." ./odoo-src
mkdir -p addons

mkdir -p .checkbox
cat > .checkbox/profile.json <<'JSON'
{
  "schema": 1,
  "odoo_version": "18.0",
  "edition": "enterprise",
  "hosting": "on-premise",
  "localizations": [],
  "odoo_source": "odoo-src",
  "enterprise_source": "odoo-src/enterprise",
  "custom_addons": ["addons"],
  "third_party_addons": [],
  "mode": "full",
  "detected": {},
  "confirmed_by_user": true
}
JSON
