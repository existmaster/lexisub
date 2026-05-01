import pytest
from lexisub.core.subtitle import Cue
from lexisub.core.translator import translate

pytestmark = pytest.mark.heavy


def test_translate_short_passage_with_glossary():
    cues = [
        Cue(1, 0, 2000, "Welcome to MMA training."),
        Cue(2, 2000, 4000, "Today we cover guard pass."),
    ]
    glossary_prompt = (
        "당신은 MMA 자막 번역가입니다. 다음 용어집을 따르세요:\n"
        "- guard pass → 가드 패스\n"
    )
    out = translate(cues, source_lang="en", system_prompt=glossary_prompt)
    assert len(out) == 2
    assert "가드 패스" in out[1].text
    assert all(o.start_ms == c.start_ms for o, c in zip(out, cues))
    assert all(o.end_ms == c.end_ms for o, c in zip(out, cues))
