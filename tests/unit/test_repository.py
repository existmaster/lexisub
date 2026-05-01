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


# --- v0.2.3 / v0.3 additions: deletion + bulk + RAG infra ---

def test_delete_term_removes_term_and_sources(tmp_db: Path):
    tid = repository.upsert_term(tmp_db, "en", "armbar", "암바", "기술", "approved")
    pid = repository.upsert_pdf(tmp_db, "/abs/x.pdf", title="X")
    repository.add_term_source(tmp_db, tid, pid, page_no=1, context="ctx")
    repository.delete_term(tmp_db, tid)
    assert repository.get_term(tmp_db, tid) is None


def test_delete_terms_bulk(tmp_db: Path):
    ids = [
        repository.upsert_term(tmp_db, "en", f"t{i}", f"용어{i}", "기술", "pending")
        for i in range(5)
    ]
    n = repository.delete_terms(tmp_db, ids[:3])
    assert n == 3
    assert len(repository.list_terms(tmp_db)) == 2


def test_delete_pdf_keeps_terms(tmp_db: Path):
    pid = repository.upsert_pdf(tmp_db, "/abs/y.pdf", title="Y")
    tid = repository.upsert_term(tmp_db, "en", "kimura", "키무라", "기술", "approved")
    repository.add_term_source(tmp_db, tid, pid, page_no=2, context="ctx")
    repository.delete_pdf(tmp_db, pid)
    assert repository.get_pdf(tmp_db, pid) is None
    assert repository.get_term(tmp_db, tid) is not None
    assert repository.list_sources_for_term(tmp_db, tid) == []


def test_prune_orphan_terms_removes_only_pending_no_sources(tmp_db: Path):
    t1 = repository.upsert_term(tmp_db, "en", "orphan_pending", "고아_보류", None, "pending")
    t2 = repository.upsert_term(tmp_db, "en", "csv_approved", "임포트_승인", None, "approved")
    t3 = repository.upsert_term(tmp_db, "en", "kept_pending", "보류_유지", None, "pending")
    pid = repository.upsert_pdf(tmp_db, "/abs/z.pdf", title="Z")
    repository.add_term_source(tmp_db, t3, pid, page_no=1, context="ctx")
    n = repository.prune_orphan_terms(tmp_db)
    assert n == 1
    assert repository.get_term(tmp_db, t1) is None
    assert repository.get_term(tmp_db, t2) is not None
    assert repository.get_term(tmp_db, t3) is not None


def test_set_terms_status_bulk(tmp_db: Path):
    ids = [
        repository.upsert_term(tmp_db, "en", f"t{i}", f"용어{i}", None, "pending")
        for i in range(4)
    ]
    n = repository.set_terms_status(tmp_db, ids[:3], "approved")
    assert n == 3
    assert len(repository.list_terms(tmp_db, status="approved")) == 3
    assert len(repository.list_terms(tmp_db, status="pending")) == 1


def test_set_all_pending_to_approved(tmp_db: Path):
    for i in range(5):
        repository.upsert_term(tmp_db, "en", f"t{i}", f"용어{i}", None, "pending")
    repository.upsert_term(tmp_db, "en", "kept", "유지", None, "approved")
    n = repository.set_all_pending_to(tmp_db, "approved")
    assert n == 5
    assert len(repository.list_terms(tmp_db, status="approved")) == 6


def test_upsert_term_with_definition(tmp_db: Path):
    tid = repository.upsert_term(
        tmp_db, "en", "Heel Strike", "발꿈치 접지", "기술", "approved",
        definition="발꿈치가 지면에 처음 닿는 보행 사이클의 시작 지점.",
    )
    row = repository.get_term(tmp_db, tid)
    assert row["definition"] == "발꿈치가 지면에 처음 닿는 보행 사이클의 시작 지점."


def test_upsert_term_definition_preserved_on_conflict(tmp_db: Path):
    tid = repository.upsert_term(
        tmp_db, "en", "Foo", "푸", None, "approved", definition="원래 정의.",
    )
    repository.upsert_term(tmp_db, "en", "Foo", "푸", None, "approved")
    row = repository.get_term(tmp_db, tid)
    assert row["definition"] == "원래 정의."


def test_pdf_chunks_crud(tmp_db: Path):
    pid = repository.upsert_pdf(tmp_db, "/abs/c.pdf", title="C")
    repository.add_pdf_chunk(tmp_db, pid, 0, "first chunk text", page_no=1)
    repository.add_pdf_chunk(tmp_db, pid, 1, "second chunk text", page_no=2)
    chunks = repository.list_chunks_for_pdf(tmp_db, pid)
    assert len(chunks) == 2
    assert chunks[0]["text"] == "first chunk text"
    assert chunks[0]["embedding"] is None
    assert repository.count_chunks(tmp_db, pid) == 2


def test_pdf_chunks_idempotent(tmp_db: Path):
    pid = repository.upsert_pdf(tmp_db, "/abs/c.pdf", title="C")
    repository.add_pdf_chunk(tmp_db, pid, 0, "x", page_no=1)
    repository.add_pdf_chunk(tmp_db, pid, 0, "y", page_no=1)
    assert repository.count_chunks(tmp_db, pid) == 1


def test_pdf_delete_cascades_chunks(tmp_db: Path):
    pid = repository.upsert_pdf(tmp_db, "/abs/c.pdf", title="C")
    repository.add_pdf_chunk(tmp_db, pid, 0, "x", page_no=1)
    repository.delete_pdf(tmp_db, pid)
    assert repository.count_chunks(tmp_db) == 0


def test_translation_pairs_crud(tmp_db: Path):
    pid = repository.upsert_pdf(tmp_db, "/abs/d.pdf", title="D")
    repository.add_translation_pair(
        tmp_db, pid, "en", "Heel strike phase", "발꿈치 접지 단계", page_no=1,
    )
    repository.add_translation_pair(
        tmp_db, pid, "en", "Toe off", "발끝 떼기", page_no=2,
    )
    assert repository.count_translation_pairs(tmp_db) == 2
    pairs = repository.list_translation_pairs(tmp_db, pid)
    assert len(pairs) == 2


def test_translation_pairs_idempotent(tmp_db: Path):
    pid = repository.upsert_pdf(tmp_db, "/abs/d.pdf", title="D")
    repository.add_translation_pair(tmp_db, pid, "en", "X", "엑스")
    repository.add_translation_pair(tmp_db, pid, "en", "X", "엑스")  # duplicate
    assert repository.count_translation_pairs(tmp_db) == 1


def test_update_term_changes_fields(tmp_db: Path):
    tid = repository.upsert_term(
        tmp_db, "en", "Eversion", "회내", "기술", "pending",
        definition="잘못된 추론.",
        evidence_level="inferred",
    )
    repository.update_term(
        tmp_db, tid,
        ko_term="외번",
        definition="발이 외측으로 회전하는 동작.",
        status="approved",
        evidence_level="user_edit",
    )
    row = repository.get_term(tmp_db, tid)
    assert row["ko_term"] == "외번"
    assert row["status"] == "approved"
    assert row["definition"] == "발이 외측으로 회전하는 동작."
    assert row["evidence_level"] == "user_edit"


def test_update_term_preserves_unspecified_fields(tmp_db: Path):
    tid = repository.upsert_term(
        tmp_db, "en", "X", "엑스", "기술", "approved",
        definition="원래 정의.",
        evidence_level="from_text",
    )
    repository.update_term(tmp_db, tid, ko_term="엑쓰")
    row = repository.get_term(tmp_db, tid)
    assert row["ko_term"] == "엑쓰"
    assert row["status"] == "approved"
    assert row["definition"] == "원래 정의."
    assert row["evidence_level"] == "from_text"


def test_csv_import_sets_evidence_csv_import(tmp_db: Path, tmp_path: Path):
    from lexisub.core import glossary as glossary_mod
    csv_path = tmp_path / "g.csv"
    csv_path.write_text(
        "source_lang,source_term,ko_term,category\n"
        "en,armbar,암바,기술\n",
        encoding="utf-8",
    )
    glossary_mod.import_csv(tmp_db, csv_path)
    rows = repository.list_terms(tmp_db)
    assert rows[0]["evidence_level"] == "csv_import"


def test_v01_db_migrates_to_definition(tmp_path: Path):
    """Simulate an old DB without `definition`: init_db should add the
    column without losing existing rows.
    """
    import sqlite3
    db = tmp_path / "old.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE terms (
              id INTEGER PRIMARY KEY,
              source_lang TEXT NOT NULL,
              source_term TEXT NOT NULL,
              ko_term TEXT NOT NULL,
              category TEXT,
              status TEXT NOT NULL DEFAULT 'pending',
              notes TEXT,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(source_lang, source_term, ko_term)
            );
            INSERT INTO terms (source_lang, source_term, ko_term, status)
            VALUES ('en', 'old_term', '옛_용어', 'approved');
            """
        )
        conn.commit()
    repository.init_db(db)  # should ALTER terms ADD definition
    rows = repository.list_terms(db)
    assert len(rows) == 1
    assert rows[0]["source_term"] == "old_term"
    assert rows[0]["definition"] is None  # migrated, value defaults NULL
