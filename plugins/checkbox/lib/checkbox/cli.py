"""argparse CLI. Subcommands delegate to modules; no logic lives here."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from checkbox import approvals as approvals_mod
from checkbox import card as card_mod
from checkbox import ladder as ladder_mod
from checkbox import mode as mode_mod
from checkbox import profile as profile_mod
from checkbox import setup as setup_mod
from checkbox.hooks import HOOK_MAIN as _HOOK_MAIN
from checkbox.knowledge import search as search_mod
from checkbox.paths import data_dir, find_project_root
from checkbox.risk import classify as classify_mod
from checkbox.risk import rules as rules_mod


def _print(data: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=False))
        return
    for key, value in data.items():
        print(f"{key}: {value}")


def cmd_doctor(args: argparse.Namespace) -> int:
    import shutil
    import sqlite3
    import subprocess

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

    # Windows Store registers a `python3.exe`/`python.exe` alias stub that
    # `shutil.which` finds and reports success for, but that errors when
    # actually run (D12). checkbox-hook already skips it when resolving a
    # hook's interpreter; this just surfaces the same risk for anyone typing
    # bare `python3` themselves.
    python3_path = shutil.which("python3")
    checks["python3_on_path"] = python3_path
    checks["python3_is_windows_store_stub"] = bool(
        python3_path and "windowsapps" in python3_path.lower()
    )

    bin_checkbox = Path(__file__).resolve().parents[2] / "bin" / "checkbox"
    checks["bin_checkbox_executable"] = (
        True if sys.platform == "win32" else os.access(bin_checkbox, os.X_OK)
    )

    # P7's checkbox-mcp is optional and not installed by default (repo
    # CLAUDE.md's ".mcp.json" section) -- absent is a normal, expected
    # state, not a failure. Report it so a red MCP connection banner isn't
    # a mystery.
    venv_python = (
        data_dir() / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python3")
    )
    if not venv_python.is_file():
        checks["mcp_venv"] = "not installed (optional; see lib/checkbox/mcp_server.py docstring)"
    else:
        probe = subprocess.run(
            [str(venv_python), "-c", "import mcp"], capture_output=True, timeout=10
        )
        checks["mcp_venv"] = "ok" if probe.returncode == 0 else "installed but `import mcp` fails"

    # D13: Claude Code MCP servers have no shell and no per-OS command
    # field, so plugins/checkbox/.mcp.json's hardcoded POSIX path can never
    # resolve here even once the venv above is installed correctly -- tell
    # Windows users what to do instead of leaving a silent red banner.
    if sys.platform == "win32":
        checks["mcp_venv"] += (
            f" -- note: .mcp.json hardcodes a POSIX venv path and can't vary "
            f"by OS, so checkbox-mcp won't connect through the plugin's own "
            f".mcp.json; register it in your own project/user MCP config "
            f"pointed at {venv_python} instead"
        )

    _print(checks, args.json)
    return 0 if checks["python_version_ok"] else 1


def cmd_profile_detect(args: argparse.Namespace) -> int:
    root = Path(args.path) if args.path else find_project_root()
    prof = profile_mod.detect(root)
    if not prof.detected:
        nested = profile_mod.find_nested_checkbox_dirs(root)
        if nested:
            names = ", ".join(str(p.relative_to(root)) for p in nested)
            print(
                f"note: no Odoo checkout found at {root}, but {names} already has a "
                f"checkbox profile -- run init from there, or\n"
                f"  `checkbox profile detect {nested[0]}`",
                file=sys.stderr,
            )
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


def cmd_card_list(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_project_root()
    decisions_dir = root / ".checkbox" / "decisions"
    cards: list[dict[str, Any]] = []
    for path in sorted(decisions_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        try:
            card = card_mod.parse(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            cards.append({"file": path.name, "error": str(exc)})
            continue
        cards.append(
            {
                "file": path.name,
                "id": card.get("id"),
                "status": card.get("status"),
                "verdict": card.get("verdict"),
                "tier": card.get("tier"),
            }
        )
    if args.status:
        cards = [c for c in cards if c.get("status") == args.status]

    if args.json:
        print(json.dumps(cards, indent=2))
        return 0
    if not cards:
        print("no cards" if not args.status else f"no cards with status: {args.status}")
        return 0
    for c in cards:
        if "error" in c:
            print(f"{c['file']}: unparseable ({c['error']})")
            continue
        print(f"{c['id']}  {c['status']:<10} {c['verdict']:<10} tier={c['tier']}  {c['file']}")
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


def cmd_rules_verify(args: argparse.Namespace) -> int:
    odoo_src = Path(args.odoo_src)
    if not odoo_src.is_dir():
        print(f"error: odoo source dir not found: {odoo_src}", file=sys.stderr)
        return 1
    errors = rules_mod.verify(args.version, odoo_src)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    overlay = rules_mod.load_version(args.version)
    models = overlay.get("models", {})
    method_count = sum(len(m.get("methods", {})) for m in models.values())
    _print(
        {"version": args.version, "models": len(models), "methods": method_count, "verified": True},
        args.json,
    )
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1
    version = args.version
    if not version and args.profile:
        prof = profile_mod.load_file(Path(args.profile))
        version = getattr(prof, "odoo_version", None)
    if not version and args.root:
        try:
            prof = profile_mod.load(Path(args.root))
            version = getattr(prof, "odoo_version", None)
        except FileNotFoundError:
            pass
    if not version:
        version = "18.0"
    result = classify_mod.classify_file(path, version)
    _print(result, args.json)
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    root = Path(args.project) if args.project else find_project_root()
    if not root.is_dir():
        print(f"error: project dir not found: {root}", file=sys.stderr)
        return 2
    try:
        report = setup_mod.install(args.host, root, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    wording = {
        "write": ("write", "written"),
        "overwrite": ("update", "updated"),
        "append": ("merge into", "merged into existing file"),
        "skip": ("skip (already present)", "already present"),
    }
    for entry in report["files"]:
        infinitive, done = wording[entry["action"]]
        verb = f"would {infinitive}" if args.dry_run else done
        print(f"{entry['target']}: {verb} ({entry['sha256'][:12]})")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else find_project_root()
    try:
        record = approvals_mod.approve(root, args.card_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print(record, args.json)
    return 0


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

    card_list = card_sub.add_parser("list", help="list decision cards, optionally by status")
    card_list.add_argument("--status", choices=card_mod.VALID_STATUSES, default=None)
    card_list.add_argument("--root", default=None)
    card_list.add_argument("--json", action="store_true")
    card_list.set_defaults(func=cmd_card_list)

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
    mode_set.add_argument("level", choices=profile_mod.VALID_MODES)
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

    rules_parser = sub.add_parser("rules", help="risk rules")
    rules_sub = rules_parser.add_subparsers(dest="rules_command", required=True)
    verify = rules_sub.add_parser(
        "verify", help="verify risk rules against a real Odoo source checkout"
    )
    verify.add_argument("--version", required=True, help="odoo version, e.g. 18.0")
    verify.add_argument("--odoo-src", required=True, help="path to odoo source checkout root")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=cmd_rules_verify)

    classify_parser = sub.add_parser("classify", help="classify a file's blast-radius tier")
    classify_parser.add_argument("path", help="file to classify")
    classify_parser.add_argument("--version", default=None, help="odoo version (e.g. 18.0)")
    classify_parser.add_argument("--profile", default=None, help="path to a profile JSON file")
    classify_parser.add_argument("--root", default=None, help="project root")
    classify_parser.add_argument("--json", action="store_true")
    classify_parser.set_defaults(func=cmd_classify)

    approve_parser = sub.add_parser(
        "approve", help="human-only: approve a card (writes approvals.json)"
    )
    approve_parser.add_argument("card_id", help="4-digit card id, e.g. 0007")
    approve_parser.add_argument("--root", default=None)
    approve_parser.add_argument("--json", action="store_true")
    approve_parser.set_defaults(func=cmd_approve)

    setup_parser = sub.add_parser(
        "setup",
        help="one-command install for non-Claude hosts (opencode, cursor, windsurf, copilot)",
    )
    setup_parser.add_argument("host", choices=setup_mod.HOSTS, help="target host")
    setup_parser.add_argument(
        "--project", default=None, help="project directory (default: discovered project root)"
    )
    setup_parser.add_argument(
        "--dry-run", action="store_true", help="print the plan without writing any file"
    )
    setup_parser.add_argument("--json", action="store_true")
    setup_parser.set_defaults(func=cmd_setup)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
