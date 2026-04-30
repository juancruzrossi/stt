from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from faster_whisper import WhisperModel


def default_cpu_threads() -> int:
    count = os.cpu_count() or 4
    return max(1, min(count, 8))


def load_model(
    model: str,
    *,
    device: str = "cpu",
    compute_type: str = "int8",
    cpu_threads: int | None = None,
    local_files_only: bool = False,
) -> WhisperModel:
    return WhisperModel(
        model,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads or default_cpu_threads(),
        local_files_only=local_files_only,
    )


def transcribe_audio(
    audio: str | Path,
    *,
    model_name: str = "small",
    language: str | None = None,
    task: str = "transcribe",
    device: str = "cpu",
    compute_type: str = "int8",
    beam_size: int = 5,
    vad_filter: bool = True,
    local_files_only: bool = False,
) -> tuple[str, object]:
    model = load_model(
        model_name,
        device=device,
        compute_type=compute_type,
        local_files_only=local_files_only,
    )
    segments, info = model.transcribe(
        str(audio),
        language=language,
        task=task,
        beam_size=beam_size,
        vad_filter=vad_filter,
        condition_on_previous_text=False,
    )
    text = join_segments(segments)
    return text, info


def transcribe_waveform(
    waveform,
    *,
    model_name: str = "small",
    language: str | None = None,
    task: str = "transcribe",
    device: str = "cpu",
    compute_type: str = "int8",
    beam_size: int = 5,
    local_files_only: bool = False,
) -> tuple[str, object]:
    model = load_model(
        model_name,
        device=device,
        compute_type=compute_type,
        local_files_only=local_files_only,
    )
    segments, info = model.transcribe(
        waveform,
        language=language,
        task=task,
        beam_size=beam_size,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 350},
        condition_on_previous_text=False,
    )
    text = join_segments(segments)
    return text, info


def join_segments(segments: Iterable[object]) -> str:
    parts = [getattr(segment, "text", "").strip() for segment in segments]
    return " ".join(part for part in parts if part).strip()
