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


def _safe_title(meta_title: str | None, path: Path) -> str:
    """Use the PDF's embedded title only if it decodes cleanly. Many PDFs
    (especially Korean publishers') store the title with broken encoding,
    which PyMuPDF surfaces as mojibake like ``ô›X É:p16``. We detect that
    and fall back to the filename stem.
    """
    if not meta_title:
        return path.stem
    s = meta_title.strip()
    if not s:
        return path.stem
    # Heuristic: if more than 30% of characters are outside Hangul / ASCII /
    # common punctuation, the title is likely a decoding artifact.
    def _ok(c: str) -> bool:
        return (
            c.isascii()
            or "가" <= c <= "힣"  # Hangul syllables
            or "ㄱ" <= c <= "ㆎ"  # Hangul jamo
            or "　" <= c <= "〿"  # CJK symbols / punctuation
            or "一" <= c <= "鿿"  # CJK ideographs (Hanja in some texts)
            or c in " \t-_·,./()[]"
        )
    bad = sum(1 for c in s if not _ok(c))
    if bad / len(s) > 0.3:
        return path.stem
    return s


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
            title=_safe_title(meta_title, path),
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
    definition: str | None = None
    evidence_level: str | None = None  # 'from_text' | 'inferred' | None


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
    "definition 필드는 본문에서 그 용어가 어떻게 정의/설명되는지 한국어로 1~2 문장 요약을 넣으세요. "
    "본문에 정의가 명시적으로 등장하지 않으면 빈 문자열로 두세요. 추측하지 마세요.\n"
    "evidence 필드: 본문에 외국어 용어와 한국어 표기가 함께(병기) 등장한 경우 'from_text', "
    "본문에는 외국어만 있고 한국어 번역은 본인이 알고 있는 표준 용어로 채운 경우 'inferred'를 넣으세요. "
    "이 필드는 사용자가 어느 항목을 추가 검증해야 하는지 판단하는 데 사용됩니다 — 정직하게 표시하세요.\n"
    "출력은 반드시 다음 JSON 배열 형식입니다:\n"
    '[{"source_lang": "en|ko|...", "source_term": "...", "ko_term": "...", "category": "기술|해부학|의학|개념|장비|인명|기타", "context": "...간단한 출처 문맥...", "definition": "...정의 또는 빈 문자열...", "evidence": "from_text|inferred"}]\n'
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
        ev_raw = (item.get("evidence") or "").strip().lower()
        ev = ev_raw if ev_raw in {"from_text", "inferred"} else None
        out.append(
            ExtractedTerm(
                source_lang=sl,
                source_term=st,
                ko_term=kt,
                category=(item.get("category") or "").strip() or None,
                context=(item.get("context") or "").strip() or None,
                definition=(item.get("definition") or "").strip() or None,
                evidence_level=ev,
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

    # Always store raw chunks for future RAG (LLM-free, fast).
    for i, (page_nos, text) in enumerate(chunks):
        repository.add_pdf_chunk(
            db_path,
            pdf_id=pdf_id,
            chunk_index=i,
            text=text,
            page_no=page_nos[0] if page_nos else None,
        )

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
                    definition=t.definition,
                    evidence_level=t.evidence_level,
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


_TRANSLATION_PAIRS_PROMPT = (
    "당신은 텍스트에서 외국어(영어 등) 표현과 그에 대응하는 한국어 번역이 "
    "나란히 병기된 쌍을 추출하는 도구입니다.\n"
    "한 문장(또는 명사구)이 외국어와 한국어로 같이 등장하면 source_text와 "
    "ko_text 쌍으로 묶으세요. 단순한 단어 한 쌍이 아니라 문장/구 단위로.\n"
    "각 쌍에 source_lang(en/pt/ja 등 ISO 639-1 코드)을 함께 출력하세요.\n"
    "출력은 반드시 JSON 배열 형식:\n"
    '[{"source_lang": "en", "source_text": "...", "ko_text": "..."}]\n'
    "쌍이 없으면 빈 배열 [] 출력. 다른 설명 없이 JSON만."
)


def extract_translation_pairs(
    pdf_path: Path,
    db_path: Path,
    progress: ProgressFn = _noop,
) -> int:
    """For PDFs that print foreign-language passages alongside Korean
    translations (e.g. medical textbooks, the user's 보행의 평가.pdf),
    extract sentence-level translation pairs.

    Stored in `translation_pairs` for future few-shot translation memory
    or RAG. Embeddings stay NULL until v0.4 wires them in.

    Returns number of pairs inserted.
    """
    pdf_path = pdf_path.resolve()
    progress("opening", 0.0)
    meta, pages = open_pdf(pdf_path)
    pdf_id = repository.upsert_pdf(
        db_path,
        file_path=str(pdf_path),
        title=meta.title,
        page_count=meta.page_count,
    )
    chunks = chunk_pages(pages, target_chars=3000)
    progress("opening", 1.0)

    inserted = 0
    for i, (page_nos, text) in enumerate(chunks):
        progress("pairs", i / max(1, len(chunks)))
        attempts = 0
        pairs: list[dict] = []
        while attempts < 3:
            attempts += 1
            try:
                raw = _generate(
                    text, system=_TRANSLATION_PAIRS_PROMPT, max_tokens=4096
                )
                cleaned = _strip_code_fence(raw)
                try:
                    data = json.loads(cleaned)
                except json.JSONDecodeError:
                    data = json.loads(_salvage_truncated_array(cleaned))
                if not isinstance(data, list):
                    raise ValueError("expected JSON array")
                pairs = [d for d in data if isinstance(d, dict)]
                break
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(
                    f"pair-chunk {i + 1}/{len(chunks)} attempt {attempts} "
                    f"failed: {e}"
                )
        else:
            continue

        for p in pairs:
            sl = (p.get("source_lang") or "").strip().lower()
            if sl not in _ALLOWED_LANGS:
                continue
            st = (p.get("source_text") or "").strip()
            kt = (p.get("ko_text") or "").strip()
            if not st or not kt or st == kt:
                continue
            repository.add_translation_pair(
                db_path,
                pdf_id=pdf_id,
                source_lang=sl,
                source_text=st,
                ko_text=kt,
                page_no=page_nos[0] if page_nos else None,
            )
            inserted += 1

    progress("pairs", 1.0)
    return inserted
