"""SQLite storage for the evidence index: FTS5 when available, LIKE fallback.

docs/ARCHITECTURE.md §7.2: "SQLite FTS5 when the Python build supports it,
otherwise a LIKE fallback. The core checks this at runtime." One table,
`documents`, whose columns match the Evidence contract in
lib/checkbox/CLAUDE.md (`score` is computed at query time, never stored).

Matching is stemmed (`porter`) and prefix-based, and falls back from
"every term" to "any term" when no document has them all -- plain FTS5
`MATCH` is exact-token AND, which returned nothing for "manager approval"
against a text saying "managers ... approve" (2026-10-11 review). A few
distinct keywords still rank better than a whole sentence.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

_SCHEMA_PLAIN = """
CREATE TABLE IF NOT EXISTS documents (
    kind TEXT NOT NULL,
    ref TEXT NOT NULL,
    line INTEGER,
    title TEXT NOT NULL,
    snippet TEXT NOT NULL,
    version TEXT NOT NULL
);
"""

_SCHEMA_FTS5 = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents USING fts5(
    kind UNINDEXED, ref UNINDEXED, line UNINDEXED, title, snippet, version UNINDEXED,
    tokenize = 'porter unicode61'
);
"""


@lru_cache(maxsize=1)
def has_fts5() -> bool:
    """Whether this Python build's sqlite3 supports the FTS5 extension.

    Cached: the answer is a property of the running interpreter/sqlite3
    build, not something that changes mid-process, and this gets called
    on every search().
    """
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        con.close()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute(_SCHEMA_FTS5 if has_fts5() else _SCHEMA_PLAIN)
    con.commit()
    return con


def clear(con: sqlite3.Connection) -> None:
    con.execute("DELETE FROM documents")
    con.commit()


def index_documents(con: sqlite3.Connection, docs: list[dict[str, Any]]) -> int:
    con.executemany(
        "INSERT INTO documents (kind, ref, line, title, snippet, version) VALUES (?,?,?,?,?,?)",
        [
            (d["kind"], d["ref"], d.get("line"), d["title"], d["snippet"], d["version"])
            for d in docs
        ],
    )
    con.commit()
    return len(docs)


def _fts5_query(query: str, joiner: str = "AND") -> str:
    """Turn free text into an FTS5 query that can't raise a syntax error.

    FTS5's MATCH syntax treats `-`, `"`, `*`, `:`, and bare NOT/AND/OR as
    operators, not literal text -- verified empirically: "on-premise" (a
    term this project's own hosting vocabulary uses) raises "no such
    column: premise", and an unbalanced quote raises "unterminated
    string". Quoting each token as its own phrase (doubling any internal
    quote) forces every character to match literally instead. The trailing
    `*` makes each phrase a prefix match ("dropship" finds "dropshipping"),
    on top of the porter stemming the table is created with ("manager"
    finds "managers", "approval" finds "approve").
    """
    quoted = [f'"{tok.replace(chr(34), chr(34) * 2)}"*' for tok in query.split()]
    return f" {joiner} ".join(quoted)


def search(con: sqlite3.Connection, query: str, limit: int = 10) -> list[dict[str, Any]]:
    if has_fts5():
        if not query.split():
            return []
        # Every term first; if no document has them all, any term, best first.
        rows: list[Any] = []
        for joiner in ("AND", "OR"):
            rows = con.execute(
                "SELECT kind, ref, line, title, snippet, version, bm25(documents) AS rank "
                "FROM documents WHERE documents MATCH ? ORDER BY rank LIMIT ?",
                (_fts5_query(query, joiner), limit),
            ).fetchall()
            if rows:
                break
        # bm25() is lower-is-better; negate so callers can treat higher score as better everywhere.
        return [
            {
                "kind": r[0],
                "ref": r[1],
                "line": r[2],
                "title": r[3],
                "snippet": r[4],
                "version": r[5],
                "score": -r[6],
            }
            for r in rows
        ]
    # Escape LIKE's own wildcards so a literal "%" or "_" in the query
    # matches literally instead of acting as a wildcard.
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{escaped}%"
    rows = con.execute(
        "SELECT kind, ref, line, title, snippet, version FROM documents "
        "WHERE title LIKE ? ESCAPE '\\' OR snippet LIKE ? ESCAPE '\\' LIMIT ?",
        (like, like, limit),
    ).fetchall()
    return [
        {
            "kind": r[0],
            "ref": r[1],
            "line": r[2],
            "title": r[3],
            "snippet": r[4],
            "version": r[5],
            "score": 1.0,
        }
        for r in rows
    ]
