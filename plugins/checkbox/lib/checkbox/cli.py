"""argparse CLI. Subcommands delegate to modules; no logic lives here."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from checkbox import profile as profile_mod
from checkbox.paths import find_project_root


def _print(data: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=False))
        return
    for key, value in data.items():
        print(f"{key}: {value}")


def cmd_doctor(args: argparse.Namespace) -> int:
    import sqlite3

    checks: dict[str, Any] = {
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "python_version_ok": sys.version_info >= (3, 10),
    }
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        checks["sqlite_fts5"] = True
    except sqlite3.OperationalError:
        checks["sqlite_fts5"] = False
    finally:
        con.close()

    root = find_project_root()
    checks["project_root"] = str(root)
    checks["profile_present"] = (root / ".checkbox" / "profile.json").is_file()

    _print(checks, args.json)
    return 0 if checks["python_version_ok"] else 1


def cmd_profile_detect(args: argparse.Namespace) -> int:
    root = Path(args.path) if args.path else find_project_root()
    prof = profile_mod.detect(root)
    _print(prof.to_dict(), args.json)
    return 0


def cmd_profile_show(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_project_root()
    try:
        prof = profile_mod.load(root)
    except FileNotFoundError:
        print(f"no profile at {root}/.checkbox/profile.json -- run /checkbox:init", file=sys.stderr)
        return 1
    _print(prof.to_dict(), args.json)
    return 0


def cmd_profile_write(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_project_root()
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"error: stdin is not valid JSON: {exc}", file=sys.stderr)
        return 2
    known = set(profile_mod.Profile.__dataclass_fields__)
    prof = profile_mod.Profile(**{k: v for k, v in data.items() if k in known})
    errors = profile_mod.validate(prof)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    path = profile_mod.write(root, prof)
    _print({"written": str(path)}, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="checkbox")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="environment sanity check")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    profile_parser = sub.add_parser("profile", help="Odoo project profile")
    profile_sub = profile_parser.add_subparsers(dest="profile_command", required=True)

    detect = profile_sub.add_parser(
        "detect", help="detect version/edition/addon paths from a checkout"
    )
    detect.add_argument(
        "path", nargs="?", default=None, help="defaults to the discovered project root"
    )
    detect.add_argument("--json", action="store_true")
    detect.set_defaults(func=cmd_profile_detect)

    show = profile_sub.add_parser("show", help="print the saved .checkbox/profile.json")
    show.add_argument("--root", default=None)
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_profile_show)

    write = profile_sub.add_parser(
        "write", help="validate and save a profile read as JSON from stdin"
    )
    write.add_argument("--root", default=None)
    write.add_argument("--json", action="store_true")
    write.set_defaults(func=cmd_profile_write)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
