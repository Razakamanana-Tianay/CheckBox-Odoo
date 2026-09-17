"""SQLite storage for the evidence index: FTS5 when available, LIKE fallback.

docs/ARCHITECTURE.md §7.2: "SQLite FTS5 when the Python build supports it,
otherwise a LIKE fallback. The core checks this at runtime." One table,
`documents`, whose columns match the Evidence contract in
lib/checkbox/CLAUDE.md (`score` is computed at query time, never stored).

FTS5's default `MATCH` is exact-token AND matching, not stemmed or fuzzy:
"manager" won't match text containing only "managers", and a multi-word
query with any non-matching token returns nothing. Verified empirically
against the real sparse-cloned 18.0 checkout while building this -- a
query has to reuse words that actually appear in the source text. Callers
(the `search` CLI, and later the `standard-scout` agent) should search with
a few distinct keywords pulled from the request, not a whole sentence.
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
    kind UNINDEXED, ref UNINDEXED, line UNINDEXED, title, snippet, version UNINDEXED
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


def _fts5_query(query: str) -> str:
    """Turn free text into an FTS5 query that can't raise a syntax error.

    FTS5's MATCH syntax treats `-`, `"`, `*`, `:`, and bare NOT/AND/OR as
    operators, not literal text -- verified empirically: "on-premise" (a
    term this project's own hosting vocabulary uses) raises "no such
    column: premise", and an unbalanced quote raises "unterminated
    string". Quoting each token as its own phrase (doubling any internal
    quote) forces every character to match literally instead.
    """
    tokens = query.split()
    return " ".join(f'"{tok.replace(chr(34), chr(34) * 2)}"' for tok in tokens)


def search(con: sqlite3.Connection, query: str, limit: int = 10) -> list[dict[str, Any]]:
    if has_fts5():
        fts_query = _fts5_query(query)
        if not fts_query:
            return []
        rows = con.execute(
            "SELECT kind, ref, line, title, snippet, version, bm25(documents) AS rank "
            "FROM documents WHERE documents MATCH ? ORDER BY rank LIMIT ?",
            (fts_query, limit),
        ).fetchall()
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
