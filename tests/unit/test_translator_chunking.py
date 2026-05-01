from mma_sub.core.subtitle import Cue
from mma_sub.core.translator import chunk_cues, format_chunk_for_llm, parse_llm_response, reassemble


def make_cues(n: int) -> list[Cue]:
    return [Cue(i + 1, i * 1000, i * 1000 + 800, f"line {i+1}") for i in range(n)]


def test_chunk_size_respected():
    cues = make_cues(60)
    chunks = list(chunk_cues(cues, size=25, context=3))
    assert len(chunks) == 3
    main_lens = [len(c.main) for c in chunks]
    assert main_lens == [25, 25, 10]


def test_chunk_includes_context():
    cues = make_cues(60)
    chunks = list(chunk_cues(cues, size=25, context=3))
    assert len(chunks[1].before) == 3
    assert chunks[1].before[-1].text == "line 25"
    assert chunks[1].main[0].text == "line 26"


def test_format_chunk_marks_main_lines():
    cues = make_cues(5)
    chunks = list(chunk_cues(cues, size=10, context=2))
    s = format_chunk_for_llm(chunks[0])
    assert "1: line 1" in s
    assert "5: line 5" in s


def test_parse_response_returns_translations_in_order():
    text = "1: 줄 일\n2: 줄 이\n3: 줄 삼\n"
    out = parse_llm_response(text, expected=3)
    assert out == ["줄 일", "줄 이", "줄 삼"]


def test_parse_response_raises_on_count_mismatch():
    import pytest
    with pytest.raises(ValueError):
        parse_llm_response("1: only one\n", expected=3)


def test_reassemble_preserves_timestamps():
    cues = make_cues(3)
    translated = ["가", "나", "다"]
    out = reassemble(cues, translated)
    assert [c.text for c in out] == ["가", "나", "다"]
    assert [c.start_ms for c in out] == [c.start_ms for c in cues]
    assert [c.end_ms for c in out] == [c.end_ms for c in cues]
