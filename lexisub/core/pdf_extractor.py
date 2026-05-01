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


_ALLOWED_LANGS = {"en", "ko", "ja", "zh-cn", "zh-tw", "es", "fr", "de", "pt", "it", "ru"}


def detect_language(text: str, fallback: str = "en") -> str:
    """Detect the dominant language of `text` and return an ISO code.

    Uses langdetect (statistical n-gram). Returns the fallback if the
    text is too short / mixed / detection raises. Result is normalized
    to a small whitelist; unknown codes fall back too.
    """
    text = (text or "").strip()
    if len(text) < 50:
        return fallback
    try:
        from langdetect import detect, DetectorFactory  # type: ignore

        DetectorFactory.seed = 0
        code = detect(text[:4000]).lower()
    except Exception:
        return fallback
    # langdetect returns "ko", "en", "zh-cn"... map and whitelist
    if code in _ALLOWED_LANGS:
        return code
    if code.startswith("zh"):
        return "zh-cn"
    return fallback


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
    """LLMs often wrap JSON in ```json ... ```. Strip if present.

    Tolerates a missing closing fence (happens when the model hits the
    token limit and the array is truncated). Also handles the inline
    single-line variant.
    """
    text = text.strip()
    closed = re.match(r"^```(?:json)?\s*\n?(.+?)\n?```\s*$", text, re.DOTALL)
    if closed:
        return closed.group(1).strip()
    open_only = re.match(r"^```(?:json)?\s*\n?(.+)$", text, re.DOTALL)
    if open_only:
        return open_only.group(1).strip()
    return text


def _salvage_truncated_array(text: str) -> str:
    """If the LLM produced a truncated JSON array (no closing `]`),
    drop the trailing partial object and close the array.

    Example input:
        [
          {"source_term": "a", "ko_term": "가"},
          {"source_term": "b", "ko_term":
    Output:
        [
          {"source_term": "a", "ko_term": "가"}
        ]
    """
    text = text.strip()
    if not text.startswith("["):
        return text
    if text.endswith("]"):
        return text
    last_close = text.rfind("}")
    if last_close == -1:
        return "[]"
    return text[: last_close + 1] + "\n]"


_SYSTEM_PROMPT = (
    "당신은 텍스트에서 도메인 전문 용어를 추출하는 도구입니다.\n"
    "사용자가 제공한 텍스트에서 다음 조건을 만족하는 용어를 찾으세요:\n"
    "1. 일반 어휘가 아닌 도메인 전문 용어 (기술 명칭, 인명에서 유래한 기법, 해부학 용어, 의학 용어 등)\n"
    "2. 다른 자료에서 일관되게 같은 한국어로 번역되어야 의미가 보존되는 용어\n"
    "각 용어에 대해 source_lang 필드에 ISO 639-1 코드(en, ko, pt, ja, fr, es, de, it, ru, zh-cn 등)를 포함하세요.\n"
    "원어가 영어 학술용어면 source_lang='en'이고 ko_term에 한국어 번역을 넣으세요.\n"
    "원어가 한국어 전문용어인데 표준 한국어 표기가 따로 있다면 source_lang='ko'로 두고 ko_term에 표준 표기를 넣으세요.\n"
    "출력은 반드시 다음 JSON 배열 형식입니다:\n"
    '[{"source_lang": "en|ko|...", "source_term": "...", "ko_term": "...", "category": "기술|해부학|의학|개념|장비|기타", "context": "...간단한 출처 문맥..."}]\n'
    "용어가 없으면 빈 배열 []을 출력하세요.\n"
    "다른 설명 없이 JSON만 출력하세요."
)


def _generate(prompt: str, system: str, max_tokens: int = 4096) -> str:
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


def _parse_terms(raw: str, default_source_lang: str) -> list[ExtractedTerm]:
    cleaned = _strip_code_fence(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            data = json.loads(_salvage_truncated_array(cleaned))
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned invalid JSON (even after salvage): {e}; "
                f"raw={raw[:200]!r}"
            )
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
        # Trust LLM-emitted source_lang if it's in the whitelist; else default.
        item_lang = (item.get("source_lang") or "").strip().lower()
        sl = item_lang if item_lang in _ALLOWED_LANGS else default_source_lang
        out.append(
            ExtractedTerm(
                source_lang=sl,
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
    source_lang: str | None = None,
    progress: ProgressFn = _noop,
) -> int:
    """Open a PDF, extract terms via LLM, store as pending in DB.

    Args:
        source_lang: ISO language hint. If None, the dominant language is
            auto-detected from the PDF text. The LLM is also asked to emit
            per-term source_lang, so a multilingual PDF can yield terms
            tagged in different languages.

    Returns number of unique terms inserted (after dedup).
    """
    pdf_path = pdf_path.resolve()
    progress("opening", 0.0)
    meta, pages = open_pdf(pdf_path)
    sample = "\n".join(p.text for p in pages[: min(3, len(pages))])
    detected_lang = source_lang or detect_language(sample, fallback="en")
    if source_lang is None:
        logger.info(f"PDF lang auto-detected: {detected_lang}")
    pdf_id = repository.upsert_pdf(
        db_path,
        file_path=str(pdf_path),
        title=meta.title,
        language=detected_lang,
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
                    raw = _generate(text, system=_SYSTEM_PROMPT, max_tokens=4096)
                    terms = _parse_terms(raw, default_source_lang=detected_lang)
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
