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


def test_insert_and_list_terms(tmp_db: Path):
    repository.upsert_term(tmp_db, "en", "guard pass", "가드 패스", "기술", "approved")
    repository.upsert_term(tmp_db, "en", "armbar", "암바", "기술", "pending")
    terms = repository.list_terms(tmp_db)
    assert len(terms) == 2


def test_list_approved_only(tmp_db: Path):
    repository.upsert_term(tmp_db, "en", "guard pass", "가드 패스", "기술", "approved")
    repository.upsert_term(tmp_db, "en", "armbar", "암바", "기술", "pending")
    approved = repository.list_terms(tmp_db, status="approved")
    assert len(approved) == 1
    assert approved[0]["source_term"] == "guard pass"


def test_upsert_idempotent_on_duplicate(tmp_db: Path):
    repository.upsert_term(tmp_db, "en", "guard pass", "가드 패스", "기술", "approved")
    repository.upsert_term(tmp_db, "en", "guard pass", "가드 패스", "기술", "approved")
    assert len(repository.list_terms(tmp_db)) == 1


def test_set_term_status(tmp_db: Path):
    tid = repository.upsert_term(tmp_db, "en", "armbar", "암바", "기술", "pending")
    repository.set_term_status(tmp_db, tid, "approved")
    term = repository.get_term(tmp_db, tid)
    assert term["status"] == "approved"
