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


def test_parse_terms_carries_definition():
    raw = (
        '[{"source_lang": "en", "source_term": "Heel Strike", '
        '"ko_term": "발꿈치 접지", "category": "기술", '
        '"context": "보행 사이클의 첫 단계.", '
        '"definition": "발꿈치가 지면에 처음 닿는 보행 사이클의 시작 지점."}]'
    )
    terms = _parse_terms(raw, default_source_lang="en")
    assert terms[0].definition == "발꿈치가 지면에 처음 닿는 보행 사이클의 시작 지점."
    assert terms[0].context == "보행 사이클의 첫 단계."


def test_parse_terms_definition_empty_string_becomes_none():
    raw = (
        '[{"source_lang": "en", "source_term": "X", "ko_term": "엑스", '
        '"category": "기타", "definition": ""}]'
    )
    terms = _parse_terms(raw, default_source_lang="en")
    assert terms[0].definition is None


def test_parse_terms_no_definition_field():
    raw = (
        '[{"source_lang": "en", "source_term": "X", "ko_term": "엑스", '
        '"category": "기타"}]'
    )
    terms = _parse_terms(raw, default_source_lang="en")
    assert terms[0].definition is None


def test_detect_evidence_from_text_when_ko_present():
    from lexisub.core.pdf_extractor import _detect_evidence
    chunk = "보행의평가\nAssessment of Gait\n발꿈치 접지는 보행 사이클의 시작이다. Heel Strike."
    assert _detect_evidence("Heel Strike", "발꿈치 접지", chunk) == "from_text"


def test_detect_evidence_inferred_when_ko_absent():
    from lexisub.core.pdf_extractor import _detect_evidence
    chunk = "Eversion is a movement of the foot away from midline."
    # LLM produced "회내" but text only has English — must be inferred
    assert _detect_evidence("Eversion", "회내", chunk) == "inferred"


def test_detect_evidence_inferred_for_english_only_pdf():
    from lexisub.core.pdf_extractor import _detect_evidence
    chunk = "The kimura is a shoulder lock named after Masahiko Kimura."
    assert _detect_evidence("kimura", "키무라", chunk) == "inferred"
