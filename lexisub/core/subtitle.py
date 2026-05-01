from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Cue:
    index: int
    start_ms: int
    end_ms: int
    text: str


_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def _ts_to_ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def _ms_to_ts(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(text: str) -> list[Cue]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("﻿\n")
    blocks = re.split(r"\n\s*\n", text)
    cues: list[Cue] = []
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split("\n")
        if lines[0].strip().isdigit():
            idx = int(lines[0].strip())
            lines = lines[1:]
        else:
            idx = len(cues) + 1
        if not lines:
            raise ValueError(f"Empty cue at index {idx}")
        m = _TIMESTAMP_RE.match(lines[0].strip())
        if not m:
            raise ValueError(f"Bad timestamp line: {lines[0]!r}")
        start = _ts_to_ms(*m.group(1, 2, 3, 4))
        end = _ts_to_ms(*m.group(5, 6, 7, 8))
        body = "\n".join(lines[1:]).strip()
        cues.append(Cue(idx, start, end, body))
    return cues


def serialize_srt(cues: list[Cue]) -> str:
    parts: list[str] = []
    for i, c in enumerate(cues, start=1):
        parts.append(
            f"{i}\n{_ms_to_ts(c.start_ms)} --> {_ms_to_ts(c.end_ms)}\n{c.text}\n"
        )
    return "\n".join(parts)
