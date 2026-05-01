from __future__ import annotations
import sqlite3
from importlib import resources
from pathlib import Path


def _read_schema() -> str:
    return resources.files("lexisub.db").joinpath("schema.sql").read_text(
        encoding="utf-8"
    )


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(_read_schema())
        conn.commit()


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def upsert_term(
    path: Path,
    source_lang: str,
    source_term: str,
    ko_term: str,
    category: str | None,
    status: str = "pending",
) -> int:
    with connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO terms (source_lang, source_term, ko_term, category, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_lang, source_term, ko_term)
            DO UPDATE SET category=excluded.category,
                          status=excluded.status,
                          updated_at=CURRENT_TIMESTAMP
            RETURNING id
            """,
            (source_lang, source_term, ko_term, category, status),
        )
        return cur.fetchone()[0]


def list_terms(path: Path, status: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM terms"
    args: tuple = ()
    if status:
        sql += " WHERE status = ?"
        args = (status,)
    sql += " ORDER BY source_lang, source_term"
    with connect(path) as conn:
        return list(conn.execute(sql, args).fetchall())


def get_term(path: Path, term_id: int) -> sqlite3.Row | None:
    with connect(path) as conn:
        return conn.execute("SELECT * FROM terms WHERE id = ?", (term_id,)).fetchone()


def set_term_status(path: Path, term_id: int, status: str) -> None:
    with connect(path) as conn:
        conn.execute(
            "UPDATE terms SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, term_id),
        )
        conn.commit()
