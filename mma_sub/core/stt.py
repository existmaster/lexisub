from __future__ import annotations
from pathlib import Path
import mlx_whisper
from mma_sub.core.subtitle import Cue
from mma_sub import config


def transcribe(audio_path: Path, model_id: str | None = None) -> tuple[list[Cue], str]:
    """Run mlx-whisper on a 16kHz mono wav and return (cues, language).

    Each segment becomes a Cue with millisecond timestamps.
    """
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=model_id or config.STT_MODEL_ID,
        word_timestamps=False,
        verbose=False,
    )
    cues: list[Cue] = []
    for i, seg in enumerate(result["segments"], start=1):
        cues.append(Cue(
            index=i,
            start_ms=int(round(seg["start"] * 1000)),
            end_ms=int(round(seg["end"] * 1000)),
            text=seg["text"].strip(),
        ))
    return cues, result.get("language", "en")
