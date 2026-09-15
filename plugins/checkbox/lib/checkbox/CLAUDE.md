# lib/checkbox: core package

Stdlib-only Python ≥ 3.10. This package is imported by hooks, so import time matters. Keep top-level imports light, and import `sqlite3`, `ast` and `xml` inside the functions that need them.

## Modules

```
__main__.py        python -m checkbox → cli.main
cli.py             argparse; subcommands delegate to modules below; no logic here
paths.py           project root discovery (.checkbox/ or git root), DATA dir resolution:
                   CHECKBOX_DATA_DIR > CLAUDE_PLUGIN_DATA > ~/.cache/checkbox
profile.py         detect(root) / load(root) / write(root, profile) / validate(profile)
mode.py            resolve(): CHECKBOX_MODE > .checkbox/local.json > profile.mode > "full"
ladder.py          render(level, profile) from rules/ladder.md + ladder.compact.md
card.py            parse(md) / validate(card, profile, approvals) / next_id(dir)
approvals.py       approve(card_id) (human CLI only), is_approved(card), card_hash(block)
session.py         .checkbox/.session/<session_id>.json read/update (touched addons, stop blocks)
risk/
  rules.py         load common.json + version overlay; verify(version, odoo_src)
  pyscan.py        ast visitor → findings
  xmlscan.py       ir.rule / ir.model.access / groups / noupdate → findings
  classify.py      classify(path|diff, profile) → {tier, reasons[]}
knowledge/
  store.py         sqlite helpers; has_fts5(); search(); LIKE fallback — shipped, P3
  source.py        build feature index from addons paths (manifests, settings fields/views) — shipped, P3.
                   _description/menu-name indexing deferred; not needed by any seed case yet
  docs.py          sparse shallow clone of odoo/documentation@version; section splitter — NOT built (deferred at P3, stayed deferred at P7, ARCHITECTURE §14 D10)
  oca.py           curated repo list; shallow clones; manifest fields — NOT built (P7 named this in scope but it was cut on review, ARCHITECTURE §14 D10 -- network+disk cost, no consumer yet)
  search.py        unified search → Evidence list — shipped, P3, `source` kind only until docs.py/oca.py land
hooks/
  common.py        read stdin JSON, safe_main() wrapper (fail-open), emit() helpers
  session_start.py prompt.py subagent_start.py pre_edit.py pre_bash.py post_edit.py stop.py
mcp_server.py      (P7, shipped) optional; imports the mcp SDK lazily; exposes search/classify/card_validate
```

## Contracts

- **Evidence**: `{"kind": "source|docs|oca|live|unverified", "ref": str, "line": int|None, "title": str, "snippet": str, "version": str, "score": float}`
- **Finding**: `{"rule_id": str, "tier": "green|amber|red", "file": str, "line": int, "detail": str}`
- **Classification**: `{"tier": ..., "reasons": [Finding, ...]}`. The highest tier wins, and the empty result is `green`.
- **Profile**: `docs/ARCHITECTURE.md` Appendix B. `validate()` returns a list of error strings; an empty list means valid.
- **Card**: the key set in ARCHITECTURE §5.1. Validation rules:
  - `verdict` is in the allowed set;
  - `tier` is required for `code` and `module`;
  - at least one non-`unverified` evidence item for `standard`, `config` and `module` (Online profiles may use `docs` only);
  - `addons` must exist under `custom_addons` when the verdict is `code`;
  - a best-effort PII lint rejects emails, IBANs and VAT-like tokens.

## Hook rules

- Every hook entry point is wrapped in `safe_main()`. On any exception it logs to stderr, prints nothing and exits 0. The strict-mode `pre-edit` deny is the only intentional block.
- **Output:** exactly one JSON object on stdout, or nothing at all.
  - Injection hooks use `hookSpecificOutput.additionalContext` with `hookEventName` set.
  - The PreToolUse deny uses `permissionDecision: "deny"` plus `permissionDecisionReason`, and the reason names the fix (`/checkbox:card`).
- **Performance:** hooks never touch `knowledge/`, and never parse more than the single file named in the tool input. `tests/test_hook_perf.py` asserts p95 < 150 ms over 50 runs on the fixtures.
- **Paths:** read `cwd` from the hook input, not `os.getcwd()`, because worktrees change it. Resolve the project root from there.
- **Approvals file:** `pre-bash` denies any command that runs `checkbox approve`, or that writes to or moves `.checkbox/approvals.json`. This is a heuristic; document its limits in the reason text.

## Odoo parsing rules

- Never import Odoo or project modules, and never `exec`/`eval` anything. Use `ast.parse` and `ElementTree` only.
- **Version:** parse `odoo/release.py` with `ast` and read the `version_info` tuple literal. Don't regex it.
- **Manifests:** `__manifest__.py` is a dict literal; use `ast.literal_eval` inside a `try`. Skip broken manifests with a warning finding; don't crash.
- **Model identity:** `_inherit` may be a string or a list, and `_name` may be absent. A class counts for a model if either field names it.
- **Settings fields:** `fields.Boolean(string=..., config_parameter=..., implied_group=...)` and `module_*` boolean fields are the high-value signals for "standard exists".

## Tests

- Unit tests use `tests/fixtures/stubs/`. These are tiny hand-written trees that mimic Odoo's layout; each file carries a header comment naming the real file it mimics.
- Tests needing real source are marked `@pytest.mark.odoo_src` and read `$ODOO17_SRC`, `$ODOO18_SRC` and `$ODOO19_SRC`.
- Every risk rule id has at least one positive and one negative fixture.
- Commands:

```bash
pytest -q tests/test_profile.py tests/test_card.py tests/risk tests/test_knowledge.py
pytest -q -m odoo_src   # with env vars set
```
