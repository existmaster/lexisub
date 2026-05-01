from __future__ import annotations
import sqlite3
from importlib import resources
from pathlib import Path


def _read_schema() -> str:
    return resources.files("mma_sub.db").joinpath("schema.sql").read_text(
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
