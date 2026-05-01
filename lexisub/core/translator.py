from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterator
from lexisub.core.subtitle import Cue


@dataclass(frozen=True)
class Chunk:
    before: list[Cue]
    main: list[Cue]
    after: list[Cue]


def chunk_cues(cues: list[Cue], size: int, context: int) -> Iterator[Chunk]:
    for i in range(0, len(cues), size):
        before = cues[max(0, i - context):i]
        main = cues[i:i + size]
        after = cues[i + size:i + size + context]
        yield Chunk(before, main, after)


def format_chunk_for_llm(chunk: Chunk) -> str:
    """Render a chunk as numbered lines.

    Context lines are prefixed with `[ctx]` and rendered before/after the
    numbered MAIN block. The LLM is told to only translate the numbered lines.

    The structure is kept identical even when context blocks are empty, so
    the model sees a consistent shape on the first chunk vs. middle chunks
    (small local LLMs are sensitive to this).
    """
    parts: list[str] = []
    parts.append("[ctx-before]")
    for c in chunk.before:
        parts.append(c.text)
    if not chunk.before:
        parts.append("(없음)")
    parts.append("[translate-these]")
    for i, c in enumerate(chunk.main, start=1):
        parts.append(f"{i}: {c.text}")
    parts.append("[ctx-after]")
    for c in chunk.after:
        parts.append(c.text)
    if not chunk.after:
        parts.append("(없음)")
    return "\n".join(parts)


_LINE_RE = re.compile(r"^\s*(\d+)\s*[:.\)]\s*(.*)$")


def parse_llm_response(text: str, expected: int) -> list[str]:
    out: dict[int, str] = {}
    for raw in text.splitlines():
        m = _LINE_RE.match(raw)
        if not m:
            continue
        idx = int(m.group(1))
        if 1 <= idx <= expected:
            out[idx] = m.group(2).strip()
    if len(out) != expected:
        missing = [i for i in range(1, expected + 1) if i not in out]
        raise ValueError(
            f"LLM returned {len(out)} lines, expected {expected}. Missing: {missing}"
        )
    return [out[i] for i in range(1, expected + 1)]


def reassemble(originals: list[Cue], translated_texts: list[str]) -> list[Cue]:
    if len(originals) != len(translated_texts):
        raise ValueError("length mismatch")
    return [
        Cue(c.index, c.start_ms, c.end_ms, t)
        for c, t in zip(originals, translated_texts, strict=True)
    ]


from lexisub import config


def _generate(prompt: str, system: str, max_tokens: int = 1024) -> str:
    """Lazy import mlx_lm so unit tests don't pay the cost."""
    from mlx_lm import load, generate
    model, tokenizer = load(config.LLM_MODEL_ID)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    chat = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    text = generate(model, tokenizer, prompt=chat, max_tokens=max_tokens, verbose=False)
    return text


def translate(
    cues: list[Cue],
    source_lang: str,
    system_prompt: str,
    chunk_size: int = config.TRANSLATION_CHUNK_LINES,
    context: int = config.TRANSLATION_CONTEXT_LINES,
) -> list[Cue]:
    """Translate a full list of cues, preserving timestamps exactly.

    On unrecoverable per-chunk failure (3 attempts exhausted), the source
    text for that chunk is kept verbatim instead of crashing — partial
    output is more useful than none.
    """
    from loguru import logger

    translated_texts: list[str] = []
    for chunk_idx, chunk in enumerate(chunk_cues(cues, size=chunk_size, context=context)):
        prompt = format_chunk_for_llm(chunk)
        n = len(chunk.main)
        max_tokens = min(4096, max(512, n * 96))
        attempts = 0
        last_err: Exception | None = None
        retry_hint = ""
        success = False
        while attempts < 3:
            attempts += 1
            try:
                response = _generate(
                    prompt
                    + retry_hint
                    + f"\n\n[translate-these] 블록의 번호 매겨진 줄을 한국어로 번역하세요. "
                    f"반드시 1번부터 {n}번까지 모든 줄을 동일한 `<번호>: <번역>` 형식으로 출력해야 합니다. "
                    f"줄을 빠뜨리지 말고, 영어 원문은 출력하지 말고, "
                    f"한국어 번역만 출력하세요.",
                    system=system_prompt,
                    max_tokens=max_tokens,
                )
                texts = parse_llm_response(response, expected=n)
                _validate_lengths(chunk.main, texts)
                translated_texts.extend(texts)
                success = True
                break
            except (ValueError, RuntimeError) as e:
                last_err = e
                retry_hint = (
                    f"\n\n[중요·재시도] 직전 출력이 잘못되었습니다 ({e}). "
                    f"반드시 1번부터 {n}번까지 모두, 누락 없이, "
                    f"`<번호>: <한국어 번역>` 형식 한 줄씩 출력하세요."
                )
        if not success:
            logger.warning(
                f"chunk {chunk_idx} ({n} cues) failed after 3 attempts: {last_err}; "
                f"falling back to source text verbatim"
            )
            translated_texts.extend(c.text for c in chunk.main)
    return reassemble(cues, translated_texts)


def _validate_lengths(originals: list[Cue], translated: list[str]) -> None:
    for o, t in zip(originals, translated, strict=True):
        if len(o.text) > 0 and len(t) > config.TRANSLATION_MAX_LENGTH_RATIO * (len(o.text) * 2):
            raise ValueError(f"output too long for: {o.text!r} -> {t!r}")
