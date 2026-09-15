"""argparse CLI. Subcommands delegate to modules; no logic lives here."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from checkbox import card as card_mod
from checkbox import ladder as ladder_mod
from checkbox import mode as mode_mod
from checkbox import profile as profile_mod
from checkbox.knowledge import search as search_mod
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


def cmd_ladder_render(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_project_root()
    try:
        prof = profile_mod.load(root)
    except FileNotFoundError:
        print(
            "no profile yet at .checkbox/profile.json -- run /checkbox:init first", file=sys.stderr
        )
        return 1
    print(ladder_mod.render(args.level, prof))
    return 0


def cmd_card_next_id(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_project_root()
    new_id = card_mod.next_id(root / ".checkbox" / "decisions")
    _print({"next_id": new_id}, args.json)
    return 0


def cmd_card_validate(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_project_root()
    path = Path(args.file)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    try:
        card = card_mod.parse(text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    profile = None
    try:
        profile = profile_mod.load(root)
    except FileNotFoundError:
        pass  # no profile -> the addons-vs-custom_addons check is skipped; the rest still runs
    errors = card_mod.validate(card, profile=profile, raw_text=text)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    _print({"valid": True, "id": card.get("id"), "verdict": card.get("verdict")}, args.json)
    return 0


def cmd_mode_show(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_project_root()
    _print({"mode": mode_mod.resolve(root)}, args.json)
    return 0


def cmd_mode_set(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_project_root()
    try:
        path = mode_mod.write_local_mode(root, args.level)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print({"written": str(path), "mode": args.level}, args.json)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    if args.profile:
        profile_file = Path(args.profile)
        prof = profile_mod.load_file(profile_file)
        project_root = profile_file.resolve().parent
    else:
        project_root = Path(args.root) if args.root else find_project_root()
        try:
            prof = profile_mod.load(project_root)
        except FileNotFoundError:
            print(
                "no profile -- pass --profile <file> or run /checkbox:init first", file=sys.stderr
            )
            return 1
    kinds = args.kind.split(",") if args.kind else None
    results = search_mod.search(prof, project_root, args.query, kinds=kinds, limit=args.limit)
    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    for result in results:
        location = result["ref"] + (f":{result['line']}" if result.get("line") else "")
        print(f"[{result['kind']}] {result['title']} -- {location}")
        if result["snippet"]:
            print(f"    {result['snippet']}")
    return 0


_HOOK_MAIN = {
    "session-start": "checkbox.hooks.session_start",
    "prompt": "checkbox.hooks.prompt",
    "subagent-start": "checkbox.hooks.subagent_start",
}


def cmd_hook(args: argparse.Namespace) -> int:
    import importlib

    module = importlib.import_module(_HOOK_MAIN[args.event])
    return int(module.main())


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

    hook = sub.add_parser("hook", help="run a hook entry point (stdin: the hook's JSON payload)")
    hook.add_argument("event", choices=sorted(_HOOK_MAIN))
    hook.set_defaults(func=cmd_hook)

    ladder_parser = sub.add_parser("ladder", help="render the ladder text")
    ladder_sub = ladder_parser.add_subparsers(dest="ladder_command", required=True)
    render = ladder_sub.add_parser("render", help="render the ladder for the saved profile")
    render.add_argument("--level", choices=("lite", "full", "strict"), default="full")
    render.add_argument("--root", default=None)
    render.set_defaults(func=cmd_ladder_render)

    card_parser = sub.add_parser("card", help="decision cards")
    card_sub = card_parser.add_subparsers(dest="card_command", required=True)

    next_id = card_sub.add_parser("next-id", help="print the next .checkbox/decisions/ card id")
    next_id.add_argument("--root", default=None)
    next_id.add_argument("--json", action="store_true")
    next_id.set_defaults(func=cmd_card_next_id)

    card_validate = card_sub.add_parser("validate", help="validate a card file")
    card_validate.add_argument("file")
    card_validate.add_argument("--root", default=None)
    card_validate.add_argument("--json", action="store_true")
    card_validate.set_defaults(func=cmd_card_validate)

    mode_parser = sub.add_parser("mode", help="policy level (off/lite/full/strict)")
    mode_sub = mode_parser.add_subparsers(dest="mode_command", required=True)

    mode_show = mode_sub.add_parser("show", help="print the resolved mode")
    mode_show.add_argument("--root", default=None)
    mode_show.add_argument("--json", action="store_true")
    mode_show.set_defaults(func=cmd_mode_show)

    mode_set = mode_sub.add_parser("set", help="write .checkbox/local.json's mode override")
    mode_set.add_argument("level", choices=("off", "lite", "full", "strict"))
    mode_set.add_argument("--root", default=None)
    mode_set.add_argument("--json", action="store_true")
    mode_set.set_defaults(func=cmd_mode_set)

    search = sub.add_parser("search", help="query the source evidence index")
    search.add_argument("query")
    search.add_argument("--profile", default=None, help="path to a profile JSON file")
    search.add_argument("--root", default=None, help="project root (ignored if --profile is set)")
    search.add_argument("--kind", default=None, help="comma-separated: source,docs,oca,live")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=cmd_search)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
