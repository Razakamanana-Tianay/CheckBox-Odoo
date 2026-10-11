#!/usr/bin/env python3
"""Download the Odoo source files a risk overlay cites, for `checkbox rules verify`.

    python3 scripts/fetch_rule_sources.py --version 19.0 --dest .odoo-src/19.0
    plugins/checkbox/bin/checkbox rules verify --version 19.0 --odoo-src .odoo-src/19.0

Fetches only the files named in `plugins/checkbox/rules/risk/<version>.json`
(`source` fields) from raw.githubusercontent.com/odoo/odoo/<version>/, so CI
and a developer without a full checkout can still run the verification that
keeps guessed model/method names out of the risk data (repo CLAUDE.md,
non-negotiable #3). Exit codes: 0 ok, 1 a cited file is missing upstream,
2 usage or network error.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = REPO_ROOT / "plugins" / "checkbox" / "rules" / "risk"
RAW_URL = "https://raw.githubusercontent.com/odoo/odoo/{version}/{path}"


def sources(version: str) -> list[str]:
    overlay = json.loads((RULES_DIR / f"{version}.json").read_text(encoding="utf-8"))
    return sorted({m["source"] for m in overlay.get("models", {}).values() if m.get("source")})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True, help="Odoo version, e.g. 18.0")
    parser.add_argument("--dest", required=True, help="directory to write the files under")
    args = parser.parse_args(argv)
    missing = 0
    for path in sources(args.version):
        dest = Path(args.dest) / path
        url = RAW_URL.format(version=args.version, path=path)
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
                body = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                print(f"error: {url}: {exc}", file=sys.stderr)
                return 2
            print(f"missing upstream: {path} ({args.version})", file=sys.stderr)
            missing += 1
            continue
        except (urllib.error.URLError, OSError) as exc:
            print(f"error: {url}: {exc}", file=sys.stderr)
            return 2
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        print(f"fetched {path}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
