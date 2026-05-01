from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import fitz  # pymupdf
from loguru import logger

from lexisub import config
from lexisub.db import repository


@dataclass(frozen=True)
class PdfPage:
    page_no: int
    text: str


@dataclass(frozen=True)
class PdfMetadata:
    title: str | None
    page_count: int


def open_pdf(path: Path) -> tuple[PdfMetadata, list[PdfPage]]:
    """Open a PDF and return its metadata + text per page (1-indexed)."""
    doc = fitz.open(str(path))
    try:
        meta_title = doc.metadata.get("title") if doc.metadata else None
        pages = [
            PdfPage(page_no=i + 1, text=doc[i].get_text("text"))
            for i in range(doc.page_count)
        ]
        meta = PdfMetadata(
            title=(meta_title or path.stem) or None,
            page_count=doc.page_count,
        )
        return meta, pages
    finally:
        doc.close()


def chunk_pages(
    pages: list[PdfPage], target_chars: int = 3000
) -> list[tuple[list[int], str]]:
    """Concatenate page texts into chunks of ~target_chars.

    Returns a list of (page_numbers, joined_text) tuples. Each chunk
    preserves which pages contributed so we can record provenance.
    """
    out: list[tuple[list[int], str]] = []
    cur_pages: list[int] = []
    cur_text: list[str] = []
    cur_len = 0
    for p in pages:
        if cur_len + len(p.text) > target_chars and cur_text:
            out.append((cur_pages, "\n".join(cur_text)))
            cur_pages, cur_text, cur_len = [], [], 0
        cur_pages.append(p.page_no)
        cur_text.append(p.text)
        cur_len += len(p.text)
    if cur_text:
        out.append((cur_pages, "\n".join(cur_text)))
    return out


@dataclass(frozen=True)
class ExtractedTerm:
    source_lang: str
    source_term: str
    ko_term: str
    category: str | None
    context: str | None


def _strip_code_fence(text: str) -> str:
    """LLMs often wrap JSON in ```json ... ```. Strip if present."""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n(.+?)\n```$", text, re.DOTALL)
    if fence:
        return fence.group(1)
    return text


_SYSTEM_PROMPT = (
    "당신은 텍스트에서 도메인 전문 용어를 추출하는 도구입니다.\n"
    "사용자가 제공한 텍스트(주로 영어)에서 다음 조건을 만족하는 용어를 찾으세요:\n"
    "1. 일반 어휘가 아닌 도메인 전문 용어 (기술 명칭, 인명에서 유래한 기법, 포지션 이름 등)\n"
    "2. 다른 자료에서 일관되게 같은 한국어로 번역되어야 의미가 보존되는 용어\n"
    "출력은 반드시 다음 JSON 배열 형식입니다:\n"
    '[{"source_term": "...", "ko_term": "...", "category": "기술|포지션|개념|장비|기타", "context": "...간단한 출처 문맥..."}]\n'
    "용어가 없으면 빈 배열 []을 출력하세요.\n"
    "다른 설명 없이 JSON만 출력하세요."
)


def _generate(prompt: str, system: str, max_tokens: int = 1024) -> str:
    from mlx_lm import load, generate

    model, tokenizer = load(config.LLM_MODEL_ID)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    chat = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    return generate(
        model, tokenizer, prompt=chat, max_tokens=max_tokens, verbose=False
    )


def _parse_terms(raw: str, source_lang: str) -> list[ExtractedTerm]:
    cleaned = _strip_code_fence(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}; raw={raw[:200]!r}")
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")
    out: list[ExtractedTerm] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        st = (item.get("source_term") or "").strip()
        kt = (item.get("ko_term") or "").strip()
        if not st or not kt:
            continue
        out.append(
            ExtractedTerm(
                source_lang=source_lang,
                source_term=st,
                ko_term=kt,
                category=(item.get("category") or "").strip() or None,
                context=(item.get("context") or "").strip() or None,
            )
        )
    return out


ProgressFn = Callable[[str, float], None]


def _noop(stage: str, frac: float) -> None: ...


def extract_terms(
    pdf_path: Path,
    db_path: Path,
    source_lang: str = "en",
    progress: ProgressFn = _noop,
) -> int:
    """Open a PDF, extract terms via LLM, store as pending in DB.

    Returns number of unique terms inserted (after dedup).
    """
    pdf_path = pdf_path.resolve()
    progress("opening", 0.0)
    meta, pages = open_pdf(pdf_path)
    pdf_id = repository.upsert_pdf(
        db_path,
        file_path=str(pdf_path),
        title=meta.title,
        language=source_lang,
        page_count=meta.page_count,
    )
    repository.set_pdf_extraction_status(db_path, pdf_id, "extracting")
    chunks = chunk_pages(pages, target_chars=3000)
    progress("opening", 1.0)

    inserted = 0
    try:
        for i, (page_nos, text) in enumerate(chunks):
            progress("extracting", i / max(1, len(chunks)))
            attempts = 0
            terms: list[ExtractedTerm] = []
            while attempts < 3:
                attempts += 1
                try:
                    raw = _generate(text, system=_SYSTEM_PROMPT, max_tokens=2048)
                    terms = _parse_terms(raw, source_lang=source_lang)
                    break
                except ValueError as e:
                    logger.warning(
                        f"chunk {i + 1}/{len(chunks)} attempt {attempts} failed: {e}"
                    )
            else:
                logger.warning(f"chunk {i + 1} skipped after 3 attempts")
                continue

            for t in terms:
                term_id = repository.upsert_term(
                    db_path,
                    source_lang=t.source_lang,
                    source_term=t.source_term,
                    ko_term=t.ko_term,
                    category=t.category,
                    status="pending",
                )
                repository.add_term_source(
                    db_path,
                    term_id=term_id,
                    pdf_id=pdf_id,
                    page_no=page_nos[0],
                    context=t.context,
                )
                inserted += 1

        progress("extracting", 1.0)
        repository.set_pdf_extraction_status(
            db_path, pdf_id, "done", extracted_at_now=True
        )
    except Exception:
        repository.set_pdf_extraction_status(db_path, pdf_id, "failed")
        raise
    progress("done", 1.0)
    return inserted
