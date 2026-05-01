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
    "당신은 강의 영상의 자막을 한국어로 번역합니다. "
    "다음 규칙을 엄격히 따르세요:\n"
    "1. 아래 용어집의 용어는 반드시 지정된 한국어로 번역합니다.\n"
    "2. 자연스러운 한국어로 번역하되, 강의 어조(설명체)를 유지합니다.\n"
    "3. 입력 줄 수와 출력 줄 수를 정확히 일치시킵니다.\n"
    "4. 줄 번호와 타임스탬프는 변경하지 않습니다 (코드가 별도로 처리합니다)."
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
