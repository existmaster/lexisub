from __future__ import annotations
import gc
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from loguru import logger
from lexisub import config
from lexisub.core import audio, stt, translator, muxer, glossary, subtitle


ProgressFn = Callable[[str, float], None]


@dataclass
class PipelineResult:
    srt_path: Path
    mkv_path: Path
    source_lang: str
    source_srt_path: Path


def _noop(stage: str, frac: float) -> None: ...


def process_video(
    video_path: Path,
    out_dir: Path,
    db_path: Path,
    progress: ProgressFn = _noop,
) -> PipelineResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem
    progress("extracting_audio", 0.0)
    wav = config.TEMP_DIR / f"{stem}.wav"
    audio.extract_wav(video_path, wav)
    progress("extracting_audio", 1.0)

    progress("stt", 0.0)
    cues, lang = stt.transcribe(wav)
    logger.info(f"STT done: {len(cues)} cues, lang={lang}")
    progress("stt", 1.0)
    source_srt_path = out_dir / f"{stem}.src.srt"
    source_srt_path.write_text(subtitle.serialize_srt(cues), encoding="utf-8")
    gc.collect()

    progress("translating", 0.0)
    full_source_text = " ".join(c.text for c in cues)
    sys_prompt = glossary.build_system_prompt(
        db_path, source_lang=lang, text=full_source_text
    )
    logger.info(
        f"system prompt: {sys_prompt.count(chr(10) + '- ')} relevant terms "
        f"(filtered from full glossary)"
    )
    translated = translator.translate(
        cues, source_lang=lang, system_prompt=sys_prompt,
    )
    progress("translating", 1.0)
    gc.collect()

    srt_path = out_dir / f"{stem}.ko.srt"
    srt_path.write_text(subtitle.serialize_srt(translated), encoding="utf-8")

    progress("muxing", 0.0)
    mkv_path = out_dir / f"{stem}.subbed.mkv"
    muxer.mux_subtitle(video_path, srt_path, mkv_path, language="kor", title="Korean")
    progress("muxing", 1.0)

    progress("done", 1.0)
    return PipelineResult(
        srt_path=srt_path,
        mkv_path=mkv_path,
        source_lang=lang,
        source_srt_path=source_srt_path,
    )
