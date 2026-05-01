import sqlite3
from pathlib import Path
import pytest
from mma_sub.db import repository


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db = tmp_path / "test.sqlite3"
    repository.init_db(db)
    return db


def test_init_creates_terms_table(tmp_db: Path):
    with sqlite3.connect(tmp_db) as c:
        rows = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {r[0] for r in rows}
    assert {"terms", "pdfs", "term_sources", "jobs"} <= names


def test_init_is_idempotent(tmp_db: Path):
    repository.init_db(tmp_db)
    repository.init_db(tmp_db)
