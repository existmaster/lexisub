from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterator
from mma_sub.core.subtitle import Cue


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
    """
    parts: list[str] = []
    if chunk.before:
        parts.append("[ctx-before]")
        for c in chunk.before:
            parts.append(c.text)
    parts.append("[translate-these]")
    for i, c in enumerate(chunk.main, start=1):
        parts.append(f"{i}: {c.text}")
    if chunk.after:
        parts.append("[ctx-after]")
        for c in chunk.after:
            parts.append(c.text)
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
