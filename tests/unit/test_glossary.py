from pathlib import Path
import pytest
from lexisub.db import repository
from lexisub.core import glossary

FIXTURE = Path(__file__).parent.parent / "fixtures" / "glossary.csv"


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db = tmp_path / "g.sqlite3"
    repository.init_db(db)
    return db


def test_import_csv_adds_rows_as_approved(tmp_db: Path):
    n = glossary.import_csv(tmp_db, FIXTURE, default_status="approved")
    assert n == 4
    rows = repository.list_terms(tmp_db, status="approved")
    assert len(rows) == 4


def test_import_csv_idempotent(tmp_db: Path):
    glossary.import_csv(tmp_db, FIXTURE)
    glossary.import_csv(tmp_db, FIXTURE)
    assert len(repository.list_terms(tmp_db)) == 4


def test_build_system_prompt_includes_only_approved(tmp_db: Path):
    glossary.import_csv(tmp_db, FIXTURE, default_status="approved")
    repository.upsert_term(tmp_db, "en", "ignored term", "무시", "기술", "pending")
    prompt = glossary.build_system_prompt(tmp_db, source_lang="en")
    assert "guard pass" in prompt
    assert "가드 패스" in prompt
    assert "ignored term" not in prompt


def test_build_system_prompt_filters_by_lang(tmp_db: Path):
    glossary.import_csv(tmp_db, FIXTURE, default_status="approved")
    en_prompt = glossary.build_system_prompt(tmp_db, source_lang="en")
    pt_prompt = glossary.build_system_prompt(tmp_db, source_lang="pt")
    assert "passagem de guarda" not in en_prompt
    assert "passagem de guarda" in pt_prompt


def test_build_system_prompt_with_no_terms_still_returns_text(tmp_db: Path):
    prompt = glossary.build_system_prompt(tmp_db, source_lang="en")
    assert "한국어" in prompt
    assert "용어집" in prompt


def test_build_system_prompt_filters_by_text(tmp_db: Path):
    glossary.import_csv(tmp_db, FIXTURE, default_status="approved")
    prompt = glossary.build_system_prompt(
        tmp_db, source_lang="en", text="he locked an armbar from guard"
    )
    assert "armbar" in prompt
    assert "guard pass" not in prompt
    assert "rear naked choke" not in prompt


def test_build_system_prompt_max_terms_cap(tmp_db: Path):
    for i in range(50):
        repository.upsert_term(
            tmp_db, "en", f"term_{i:02d}", f"용어_{i:02d}", "기술", "approved"
        )
    prompt = glossary.build_system_prompt(tmp_db, source_lang="en", max_terms=40)
    line_count = prompt.count("\n- ")
    assert line_count == 40
