import sqlite3
from pathlib import Path
import pytest
from lexisub.db import repository


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


def test_upsert_pdf_and_list(tmp_db: Path):
    pid = repository.upsert_pdf(
        tmp_db, "/abs/path/foo.pdf", title="Foo", language="en", page_count=10
    )
    assert pid > 0
    pdfs = repository.list_pdfs(tmp_db)
    assert len(pdfs) == 1
    assert pdfs[0]["title"] == "Foo"


def test_upsert_pdf_idempotent(tmp_db: Path):
    repository.upsert_pdf(tmp_db, "/abs/foo.pdf", title="Foo")
    repository.upsert_pdf(tmp_db, "/abs/foo.pdf", title="Foo Updated")
    pdfs = repository.list_pdfs(tmp_db)
    assert len(pdfs) == 1
    assert pdfs[0]["title"] == "Foo Updated"


def test_set_pdf_extraction_status(tmp_db: Path):
    pid = repository.upsert_pdf(tmp_db, "/abs/bar.pdf", title="Bar")
    repository.set_pdf_extraction_status(tmp_db, pid, "extracting")
    assert repository.get_pdf(tmp_db, pid)["extraction_status"] == "extracting"
    repository.set_pdf_extraction_status(tmp_db, pid, "done", extracted_at_now=True)
    row = repository.get_pdf(tmp_db, pid)
    assert row["extraction_status"] == "done"
    assert row["extracted_at"] is not None


def test_add_and_list_term_sources(tmp_db: Path):
    tid = repository.upsert_term(tmp_db, "en", "armbar", "암바", "기술", "approved")
    pid = repository.upsert_pdf(tmp_db, "/abs/baz.pdf", title="Baz")
    repository.add_term_source(tmp_db, tid, pid, page_no=3, context="armbar from guard")
    sources = repository.list_sources_for_term(tmp_db, tid)
    assert len(sources) == 1
    assert sources[0]["page_no"] == 3
    assert sources[0]["pdf_title"] == "Baz"


def test_term_source_idempotent_on_same_page(tmp_db: Path):
    tid = repository.upsert_term(tmp_db, "en", "armbar", "암바", "기술", "approved")
    pid = repository.upsert_pdf(tmp_db, "/abs/baz.pdf", title="Baz")
    repository.add_term_source(tmp_db, tid, pid, page_no=3, context="ctx")
    repository.add_term_source(tmp_db, tid, pid, page_no=3, context="ctx2")
    assert len(repository.list_sources_for_term(tmp_db, tid)) == 1
