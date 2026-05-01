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


def upsert_pdf(
    path: Path,
    file_path: str,
    title: str | None = None,
    language: str | None = None,
    page_count: int | None = None,
) -> int:
    with connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO pdfs (path, title, language, page_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title=excluded.title,
                language=excluded.language,
                page_count=excluded.page_count
            RETURNING id
            """,
            (file_path, title, language, page_count),
        )
        return cur.fetchone()[0]


def list_pdfs(path: Path) -> list[sqlite3.Row]:
    with connect(path) as conn:
        return list(conn.execute(
            "SELECT * FROM pdfs ORDER BY added_at DESC"
        ).fetchall())


def get_pdf(path: Path, pdf_id: int) -> sqlite3.Row | None:
    with connect(path) as conn:
        return conn.execute(
            "SELECT * FROM pdfs WHERE id = ?", (pdf_id,)
        ).fetchone()


def set_pdf_extraction_status(
    path: Path, pdf_id: int, status: str, extracted_at_now: bool = False
) -> None:
    sql = "UPDATE pdfs SET extraction_status = ?"
    args: tuple = (status,)
    if extracted_at_now:
        sql += ", extracted_at = CURRENT_TIMESTAMP"
    sql += " WHERE id = ?"
    args = args + (pdf_id,)
    with connect(path) as conn:
        conn.execute(sql, args)
        conn.commit()


def add_term_source(
    path: Path,
    term_id: int,
    pdf_id: int,
    page_no: int | None,
    context: str | None,
) -> None:
    with connect(path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO term_sources (term_id, pdf_id, page_no, context)
            VALUES (?, ?, ?, ?)
            """,
            (term_id, pdf_id, page_no, context),
        )
        conn.commit()


def list_sources_for_term(path: Path, term_id: int) -> list[sqlite3.Row]:
    with connect(path) as conn:
        return list(conn.execute(
            """
            SELECT ts.*, p.title AS pdf_title, p.path AS pdf_path
            FROM term_sources ts
            JOIN pdfs p ON p.id = ts.pdf_id
            WHERE ts.term_id = ?
            ORDER BY ts.page_no
            """,
            (term_id,),
        ).fetchall())
