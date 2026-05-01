from pathlib import Path
import pytest
from lexisub.db import repository
from lexisub.core.pdf_extractor import extract_terms

pytestmark = pytest.mark.heavy


def test_extract_terms_from_sample_pdf(sample_pdf: Path, tmp_path: Path):
    db = tmp_path / "p.sqlite3"
    repository.init_db(db)
    n = extract_terms(sample_pdf, db, source_lang="en")
    # Sample PDF mentions: guard pass, armbar, kimura, rear naked choke
    # We expect at least one of these to be extracted
    assert n >= 1
    rows = repository.list_terms(db, status="pending")
    src_terms = {r["source_term"].lower() for r in rows}
    assert any(
        kw in src_terms or any(kw in t for t in src_terms)
        for kw in ["guard pass", "armbar", "kimura", "rear naked choke"]
    )
    # PDF row exists with extraction_status='done'
    pdfs = repository.list_pdfs(db)
    assert len(pdfs) == 1
    assert pdfs[0]["extraction_status"] == "done"
