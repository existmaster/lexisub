from pathlib import Path
from lexisub.core.pdf_extractor import (
    open_pdf, chunk_pages, PdfPage, detect_language, _parse_terms,
)


def test_open_pdf_returns_metadata_and_pages(sample_pdf: Path):
    meta, pages = open_pdf(sample_pdf)
    assert meta.page_count == 2
    assert len(pages) == 2
    assert pages[0].page_no == 1
    assert "Guard Pass" in pages[0].text
    assert "kimura" in pages[1].text.lower()


def test_chunk_pages_combines_short_pages():
    pages = [
        PdfPage(1, "short page one"),
        PdfPage(2, "short page two"),
        PdfPage(3, "short page three"),
    ]
    chunks = chunk_pages(pages, target_chars=100)
    assert len(chunks) == 1
    assert chunks[0][0] == [1, 2, 3]


def test_chunk_pages_splits_long_pages():
    pages = [
        PdfPage(1, "x" * 2500),
        PdfPage(2, "y" * 2500),
        PdfPage(3, "z" * 2500),
    ]
    chunks = chunk_pages(pages, target_chars=3000)
    assert len(chunks) == 3
    assert chunks[0][0] == [1]
    assert chunks[1][0] == [2]
    assert chunks[2][0] == [3]


def test_detect_language_english():
    en_text = (
        "The guard pass is a fundamental BJJ technique used to advance "
        "from inside the opponent's guard to side control. Common methods "
        "include the over-under pass and the toreando pass."
    )
    assert detect_language(en_text) == "en"


def test_detect_language_korean():
    ko_text = (
        "보행은 전방으로 넘어지는 동작과 그것을 바로잡는 간단한 동작입니다. "
        "한 다리는 사이클 동안 항상 지면에 닿아 있고, 한 번의 한 다리 지지 기간과 "
        "두 번의 두 다리 지지 기간이 있습니다."
    )
    assert detect_language(ko_text) == "ko"


def test_detect_language_short_text_falls_back():
    assert detect_language("hi", fallback="en") == "en"
    assert detect_language("", fallback="ko") == "ko"


def test_parse_terms_uses_llm_emitted_source_lang():
    raw = (
        '[{"source_lang": "en", "source_term": "armbar", "ko_term": "암바", '
        '"category": "기술"}, '
        '{"source_lang": "pt", "source_term": "armada", "ko_term": "암바", '
        '"category": "기술"}]'
    )
    terms = _parse_terms(raw, default_source_lang="en")
    assert len(terms) == 2
    assert terms[0].source_lang == "en"
    assert terms[1].source_lang == "pt"


def test_parse_terms_falls_back_when_lang_missing():
    raw = '[{"source_term": "armbar", "ko_term": "암바", "category": "기술"}]'
    terms = _parse_terms(raw, default_source_lang="ko")
    assert terms[0].source_lang == "ko"


def test_parse_terms_rejects_invalid_lang_code():
    raw = (
        '[{"source_lang": "klingon", "source_term": "armbar", '
        '"ko_term": "암바", "category": "기술"}]'
    )
    terms = _parse_terms(raw, default_source_lang="en")
    assert terms[0].source_lang == "en"
