# Contributing

`CLAUDE.md` at the repo root is the actual source of truth for how this
project works -- non-negotiables, repo map, commands, workflow, conventions,
and definition of done. Read it first; this file is just the practical
on-ramp for an outside PR.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
```

## Before opening a PR

```bash
ruff check . && ruff format --check .
pytest -q
claude plugin validate plugins/checkbox   # no --strict, see its own header
claude plugin validate . --strict
python3 scripts/check_rule_copies.py
```

All five must pass -- CI runs the same commands on every PR. If you touched
`plugins/checkbox/rules/`, `plugins/checkbox/bin/checkbox`, or anything
under `plugins/checkbox/lib/checkbox/`, run
`python3 scripts/build_adapters.py` first and commit the regenerated
`adapters/` -- the drift check above fails otherwise.

## The rules that actually matter

- **The core is stdlib-only.** No third-party imports under
  `plugins/checkbox/lib/checkbox/`, except the lazily-imported `mcp` module.
  Dev tools go in `pyproject.toml`, never the runtime core.
- **No Odoo fact without a source.** A model, method, module, setting or
  menu path added to `rules/`, `skills/`, `evals/` or tests must be checked
  against real Odoo source or the official docs for that version. If you
  can't verify it, write `TODO(verify)` and say so in the PR -- don't guess.
  For risk rules specifically, run `checkbox rules verify`.
- **Deterministic first.** Profile detection, card validation, risk tiering
  and guards are plain code with tests, never an LLM prompt.
- **Don't add a dependency, or vendor Ponytail's rule text.** We follow its
  delivery pattern and credit it in the README; its text is not ours.
- **Don't put client code or client data in this repo**, in a fixture, a
  test, or a commit message -- fixtures are tiny hand-written stubs, not
  real projects.

`CLAUDE.md`'s "Don't" section has the full list, including the guard/card
boundaries an agent must never cross.

## Odoo facts and Claude Code behavior

Anything added to `rules/` needs a real citation (source path, or an
official doc URL). Anything claimed about Claude Code's own behavior
(hooks, plugins, MCP config) needs a link to code.claude.com/docs and the
date you checked it -- `docs/ARCHITECTURE.md`'s decision log (D1-D13) shows
the expected level of rigor and is the right place to add a new decision if
your change makes one.

## Scope

One phase (`docs/ARCHITECTURE.md` §13) per PR where practical. If a bug
report doesn't cleanly map to a phase, that's fine -- just keep the diff
focused on the bug.

## License

MIT (see `LICENSE`). Contributions are accepted under the same license.
