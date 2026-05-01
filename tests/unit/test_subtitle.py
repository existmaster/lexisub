from mma_sub.core.subtitle import Cue, parse_srt, serialize_srt

SAMPLE = """1
00:00:01,000 --> 00:00:03,500
Welcome to MMA training.

2
00:00:04,000 --> 00:00:06,000
Today we cover guard pass.
"""


def test_parse_two_cues():
    cues = parse_srt(SAMPLE)
    assert len(cues) == 2
    assert cues[0].start_ms == 1000
    assert cues[0].end_ms == 3500
    assert cues[0].text == "Welcome to MMA training."
    assert cues[1].text == "Today we cover guard pass."


def test_parse_handles_crlf():
    cues = parse_srt(SAMPLE.replace("\n", "\r\n"))
    assert len(cues) == 2


def test_parse_multi_line_text():
    src = "1\n00:00:01,000 --> 00:00:03,000\nLine one\nLine two\n"
    cues = parse_srt(src)
    assert cues[0].text == "Line one\nLine two"


def test_serialize_roundtrip():
    cues = parse_srt(SAMPLE)
    out = serialize_srt(cues)
    again = parse_srt(out)
    assert [c.text for c in again] == [c.text for c in cues]
    assert [c.start_ms for c in again] == [c.start_ms for c in cues]


def test_parse_rejects_bad_timestamp():
    import pytest
    with pytest.raises(ValueError):
        parse_srt("1\nbad timestamp\nhi\n")
