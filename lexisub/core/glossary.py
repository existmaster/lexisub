from __future__ import annotations
import csv
from pathlib import Path
from lexisub.db import repository


def import_csv(db_path: Path, csv_path: Path, default_status: str = "approved") -> int:
    count = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"source_lang", "source_term", "ko_term"}
        if not required <= set(reader.fieldnames or []):
            missing = required - set(reader.fieldnames or [])
            raise ValueError(f"CSV missing columns: {missing}")
        for row in reader:
            repository.upsert_term(
                db_path,
                source_lang=row["source_lang"].strip(),
                source_term=row["source_term"].strip(),
                ko_term=row["ko_term"].strip(),
                category=(row.get("category") or "").strip() or None,
                status=default_status,
            )
            count += 1
    return count


_PREAMBLE = (
    "당신은 강의 영상의 영어 자막을 자연스러운 한국어로 옮기는 번역가입니다. "
    "결과물은 직역체가 아닌, 한국어 강의 스크립트로 들어도 어색하지 않은 문장이어야 합니다.\n\n"
    "[필수 규칙]\n"
    "1. 아래 용어집의 용어는 반드시 지정된 한국어로 번역합니다.\n"
    "2. 입력 줄 수와 출력 줄 수를 정확히 일치시킵니다.\n"
    "3. 줄 번호와 타임스탬프는 변경하지 않습니다 (코드가 별도 처리).\n\n"
    "[한국어 강의체 가이드 — 직역 금지]\n"
    "• 영어 대명사(he/she/they/his/their)는 한국어에서 거의 생략합니다. "
    "  필요할 때만 인물 이름이나 역할(\"공격자\", \"수비자\")로 대체.\n"
    "• \"~할 것입니다\", \"~할 수 있습니다\"의 will/can 직역을 남발하지 말고, "
    "  단순 현재형 \"~합니다\", \"~죠\" 위주로.\n"
    "• \"~을 사용하여\" → \"~로\", \"~을 활용해\".\n"
    "• \"~에 대해 말할 때\" → \"~을 보면\", \"~의 경우\".\n"
    "• 어미는 강의체 \"~합니다/이죠/봅시다\" 일관 유지.\n\n"
    "[번역 예시]\n"
    "원문: \"He uses his legs to create the bridge.\"\n"
    "나쁜 번역(직역): \"그는 그의 다리를 사용하여 브릿지를 만듭니다.\"\n"
    "좋은 번역: \"다리로 브릿지를 만듭니다.\"\n\n"
    "원문: \"Tyler's on his back here, let's take a look.\"\n"
    "나쁜 번역: \"타일러가 그의 뒤에 있습니다, 한번 봅시다.\"\n"
    "좋은 번역: \"타일러가 등을 대고 누웠죠. 한번 보시죠.\"\n\n"
    "원문: \"We're going to try to pin his upper body.\"\n"
    "나쁜 번역: \"우리는 그의 상체를 핀 상태로 만들 것입니다.\"\n"
    "좋은 번역: \"상체를 눌러 고정합니다.\""
)


def _filter_relevant(
    rows: list, text: str | None
) -> list:
    """If `text` is given, keep only terms whose source_term appears in it
    (case-insensitive substring match). Drastically shrinks the prompt for
    long glossaries when most terms aren't relevant to the current chunk.
    """
    if text is None:
        return rows
    src_lower = text.lower()
    return [r for r in rows if r["source_term"].lower() in src_lower]


def build_system_prompt(
    db_path: Path,
    source_lang: str,
    text: str | None = None,
    max_terms: int = 40,
) -> str:
    """Build the translator system prompt.

    If `text` is provided, only glossary terms that actually appear in
    `text` are included — keeps the prompt small and the model's
    instruction-following stable on local 4-bit models.
    """
    rows = [
        r for r in repository.list_terms(db_path, status="approved")
        if r["source_lang"] == source_lang
    ]
    rows = _filter_relevant(rows, text)
    if len(rows) > max_terms:
        rows = rows[:max_terms]
    if not rows:
        return _PREAMBLE + "\n\n(용어집 없음)"
    lines = ["\n\n[용어집]"]
    for r in rows:
        cat = f" ({r['category']})" if r["category"] else ""
        lines.append(f"- {r['source_term']} → {r['ko_term']}{cat}")
    return _PREAMBLE + "\n".join(lines)
